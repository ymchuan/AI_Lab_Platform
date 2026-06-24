from __future__ import annotations

import unittest
import json
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

from services.rag.chunking import discover_markdown_files, split_markdown
from services.rag.index_store import load_index, cosine_similarity, retrieve, save_index
from services.rag.pipeline import expand_query
from services.rag.server import RagServiceConfig, config_from_args, create_server, parse_args


class RagCoreTest(unittest.TestCase):
    def test_split_markdown_preserves_source_and_titles(self) -> None:
        text = (
            "# Title\n\n"
            "Intro text with enough detail about the LabAgent routing baseline, "
            "the public gateway, local model nodes, and why chunks should contain "
            "usable evidence instead of only a heading.\n\n"
            "## Details\n\n"
            "More text about routing and embedding. This section describes how "
            "embed-local creates vectors, how qwen-agent answers with citations, "
            "and why retrieval should return evidence-rich chunks."
        )

        chunks = split_markdown("docs/example.md", text, max_chars=220, overlap_chars=20)

        self.assertTrue(chunks)
        self.assertEqual(chunks[0].source_path, "docs/example.md")
        self.assertTrue(any(chunk.title == "Details" for chunk in chunks))
        self.assertTrue(all(chunk.id.startswith("docs/example.md#") for chunk in chunks))

    def test_split_markdown_skips_heading_only_chunks(self) -> None:
        text = "# Title\n\nTiny intro.\n\n## Thin\n\nshort"

        chunks = split_markdown("docs/thin.md", text, max_chars=500, overlap_chars=20)

        self.assertEqual(chunks, [])

    def test_split_markdown_rejects_invalid_window_settings(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_chars"):
            split_markdown("docs/example.md", "text", max_chars=0, overlap_chars=0)
        with self.assertRaisesRegex(ValueError, "overlap_chars"):
            split_markdown("docs/example.md", "text", max_chars=100, overlap_chars=-1)
        with self.assertRaisesRegex(ValueError, "overlap_chars"):
            split_markdown("docs/example.md", "text", max_chars=100, overlap_chars=100)

    def test_expand_query_adds_project_routing_entities(self) -> None:
        expanded = expand_query("LabAgent 当前多节点路由是什么状态？")

        self.assertIn("qwen-agent", expanded)
        self.assertIn("embed-local", expanded)
        self.assertIn(":12340", expanded)

    def test_cosine_similarity_and_retrieve_rank_expected_chunk(self) -> None:
        index = {
            "version": 1,
            "chunks": [
                {
                    "id": "a#0",
                    "source_path": "a.md",
                    "title": "Gateway",
                    "ordinal": 0,
                    "text": "LiteLLM gateway",
                    "embedding": [1.0, 0.0],
                },
                {
                    "id": "b#0",
                    "source_path": "b.md",
                    "title": "Embedding",
                    "ordinal": 0,
                    "text": "Embedding node",
                    "embedding": [0.0, 1.0],
                },
            ],
        }

        self.assertEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        results = retrieve(index, [0.0, 0.9], top_k=1)

        self.assertEqual(results[0]["id"], "b#0")

    def test_load_index_rejects_inconsistent_metadata(self) -> None:
        import tempfile

        index = {
            "version": 1,
            "embedding_model": "embed-local",
            "embedding_dimensions": 2,
            "chunk_count": 1,
            "chunks": [
                {
                    "id": "a#0",
                    "source_path": "a.md",
                    "title": "A",
                    "ordinal": 0,
                    "text": "A",
                    "embedding": [1.0, 0.0],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"
            save_index(index, path)
            self.assertEqual(load_index(path, expected_embedding_model="embed-local")["chunk_count"], 1)

            with self.assertRaisesRegex(ValueError, "embedding model mismatch"):
                load_index(path, expected_embedding_model="other-model")

            broken_count = dict(index, chunk_count=2)
            save_index(broken_count, path)
            with self.assertRaisesRegex(ValueError, "chunk_count mismatch"):
                load_index(path)

            broken_dimension = dict(index)
            broken_dimension["chunks"] = [dict(index["chunks"][0], embedding=[1.0])]
            save_index(broken_dimension, path)
            with self.assertRaisesRegex(ValueError, "embedding dimension"):
                load_index(path)

    def test_retrieve_can_use_query_text_to_boost_project_entities(self) -> None:
        index = {
            "version": 1,
            "chunks": [
                {
                    "id": "generic#0",
                    "source_path": "generic.md",
                    "title": "Generic",
                    "ordinal": 0,
                    "text": "LabAgent general documentation.",
                    "embedding": [0.9, 0.1],
                },
                {
                    "id": "route#0",
                    "source_path": "route.md",
                    "title": "Architecture",
                    "ordinal": 0,
                    "text": "qwen-agent uses :12340 on 5090 and embed-local uses :12341 on the new device.",
                    "embedding": [0.86, 0.14],
                },
            ],
        }

        results = retrieve(index, [1.0, 0.0], top_k=1, query_text="当前多节点路由是什么状态？")

        self.assertEqual(results[0]["id"], "route#0")

    def test_discover_markdown_files_skips_env_like_paths(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            (tmp_path / "README.md").write_text("ok", encoding="utf-8")
            (tmp_path / ".env.md").write_text("secret", encoding="utf-8")
            docs = tmp_path / "docs"
            docs.mkdir()
            (docs / "A.md").write_text("doc", encoding="utf-8")
            (docs / "CODE_REVIEW_ISSUES.md").write_text("raw review", encoding="utf-8")
            (docs / "claude-fable-5.md").write_text("raw prompt", encoding="utf-8")

            files = discover_markdown_files(tmp_path, ["*.md", "docs/*.md"])
            relatives = [path.relative_to(tmp_path).as_posix() for path in files]

        self.assertIn("README.md", relatives)
        self.assertIn("docs/A.md", relatives)
        self.assertNotIn(".env.md", relatives)
        self.assertNotIn("docs/CODE_REVIEW_ISSUES.md", relatives)
        self.assertNotIn("docs/claude-fable-5.md", relatives)

    def test_rag_server_health_and_auth(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            index_path = tmp_path / "index.json"
            save_index(
                {
                    "version": 1,
                    "created_at": "2026-06-22T00:00:00",
                    "embedding_model": "embed-local",
                    "embedding_dimensions": 2,
                    "chunk_count": 1,
                    "source_files": ["README.md"],
                    "source_patterns": ["README.md"],
                    "chunks": [
                        {
                            "id": "README.md#0",
                            "source_path": "README.md",
                            "title": "Intro",
                            "ordinal": 0,
                            "text": "LabAgent RAG service",
                            "embedding": [1.0, 0.0],
                        }
                    ],
                },
                index_path,
            )
            config = RagServiceConfig(
                host="127.0.0.1",
                port=0,
                embedding_base_url="http://127.0.0.1:9/v1",
                chat_base_url="http://127.0.0.1:10/v1",
                api_key=None,
                embedding_model="embed-local",
                chat_model="qwen-agent",
                rag_model="labagent-rag",
                index_path=index_path,
                service_api_key="secret",
                timeout=1,
            )
            server = create_server(config)
            try:
                port = server.server_port
                import threading

                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()

                with self.assertRaises(HTTPError) as unauthorized:
                    request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                self.assertEqual(unauthorized.exception.code, 401)

                health = http_json(
                    f"http://127.0.0.1:{port}/health",
                    headers={"Authorization": "Bearer secret"},
                )
                self.assertTrue(health["ok"])
                self.assertEqual(health["chunk_count"], 1)

                sources = http_json(
                    f"http://127.0.0.1:{port}/v1/rag/sources",
                    headers={"Authorization": "Bearer secret"},
                )
                self.assertEqual(sources["source_files"], ["README.md"])
            finally:
                server.shutdown()
                server.server_close()

    def test_rag_server_can_configure_separate_embedding_and_chat_urls(self) -> None:
        args = parse_args(
            [
                "--base-url",
                "http://gateway.example/v1",
                "--embed-base-url",
                "http://embed.example/v1",
                "--chat-base-url",
                "http://chat.example/v1",
            ]
        )
        config = config_from_args(args)

        self.assertEqual(config.embedding_base_url, "http://embed.example/v1")
        self.assertEqual(config.chat_base_url, "http://chat.example/v1")

    def test_rag_server_defaults_separate_urls_to_base_url(self) -> None:
        args = parse_args(["--base-url", "http://gateway.example/v1"])
        config = config_from_args(args)

        self.assertEqual(config.embedding_base_url, "http://gateway.example/v1")
        self.assertEqual(config.chat_base_url, "http://gateway.example/v1")


def http_json(
    url: str,
    payload: dict | None = None,
    headers: dict | None = None,
) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with request.urlopen(req, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
