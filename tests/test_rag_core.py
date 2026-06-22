from __future__ import annotations

import unittest
from pathlib import Path

from services.rag.chunking import discover_markdown_files, split_markdown
from services.rag.index_store import cosine_similarity, retrieve
from services.rag.pipeline import expand_query


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

            files = discover_markdown_files(tmp_path, ["*.md", "docs/*.md"])
            relatives = [path.relative_to(tmp_path).as_posix() for path in files]

        self.assertIn("README.md", relatives)
        self.assertIn("docs/A.md", relatives)
        self.assertNotIn(".env.md", relatives)


if __name__ == "__main__":
    unittest.main()
