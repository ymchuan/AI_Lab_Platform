from __future__ import annotations

import unittest

from services.agent.router import (
    build_final_messages,
    chat_completion_to_sse_events,
    decide_route,
    last_user_text,
    responses_input_to_messages,
)


class AgentRouterTest(unittest.TestCase):
    def test_decide_route_uses_vision_for_image_blocks(self) -> None:
        decision = decide_route(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this screenshot?"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                    ],
                }
            ]
        )

        self.assertTrue(decision.use_vision)
        self.assertFalse(decision.use_rag)

    def test_decide_route_uses_rag_for_labagent_project_questions(self) -> None:
        decision = decide_route(
            [
                {
                    "role": "user",
                    "content": "LabAgent 当前多节点路由是什么状态？",
                }
            ]
        )

        self.assertFalse(decision.use_vision)
        self.assertTrue(decision.use_rag)

    def test_decide_route_direct_chat_for_generic_questions(self) -> None:
        decision = decide_route([{"role": "user", "content": "Write a tiny Python add function."}])

        self.assertFalse(decision.use_vision)
        self.assertFalse(decision.use_rag)
        self.assertEqual(decision.reason, "direct_chat")

    def test_responses_input_to_messages_converts_text_and_image_blocks(self) -> None:
        messages = responses_input_to_messages(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Read this image"},
                        {"type": "input_image", "image_url": "data:image/png;base64,abc"},
                    ],
                }
            ]
        )

        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"][0]["type"], "text")
        self.assertEqual(messages[0]["content"][1]["type"], "image_url")

    def test_last_user_text_extracts_text_from_multimodal_message(self) -> None:
        text = last_user_text(
            [
                {"role": "system", "content": "system"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                    ],
                },
            ]
        )

        self.assertEqual(text, "Describe this")

    def test_build_final_messages_includes_side_channel_outputs(self) -> None:
        messages = build_final_messages(
            original_user_text="What is the current route?",
            vision_summary="The screenshot shows an error.",
            vision_error=None,
            rag_answer="qwen-agent is on 5090 [S1].",
            rag_error=None,
            rag_sources=[{"source_path": "README.md", "title": "Status", "score": 0.9}],
            route_reason="image_input+project_context",
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("VISION SUMMARY", messages[1]["content"])
        self.assertIn("RAG ANSWER", messages[1]["content"])
        self.assertIn("README.md", messages[1]["content"])

    def test_build_final_messages_includes_side_channel_failures(self) -> None:
        messages = build_final_messages(
            original_user_text="Check this screenshot and project state.",
            vision_summary="",
            vision_error="vision endpoint unavailable",
            rag_answer="",
            rag_error="embedding backend returned HTTP 400",
            rag_sources=[],
            route_reason="image_input+project_context",
        )

        self.assertIn("VISION ERROR", messages[1]["content"])
        self.assertIn("RAG ERROR", messages[1]["content"])

    def test_chat_completion_to_sse_events_wraps_non_stream_response(self) -> None:
        events = chat_completion_to_sse_events(
            {
                "id": "chatcmpl-test",
                "created": 123,
                "model": "labagent-agent",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            }
        )

        self.assertEqual(events[0]["choices"][0]["delta"]["role"], "assistant")
        self.assertEqual(events[1]["choices"][0]["delta"]["content"], "ok")
        self.assertEqual(events[2]["choices"][0]["finish_reason"], "stop")


if __name__ == "__main__":
    unittest.main()
