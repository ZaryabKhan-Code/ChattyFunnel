import httpx
from typing import List, Dict, Any, Optional
import logging
from app.models import AISettings, Message, MessageDirection

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered auto-responses using OpenAI or Anthropic"""

    async def generate_response(
        self,
        ai_settings: AISettings,
        conversation_history: List[Message],
        participant_name: str
    ) -> Optional[str]:
        """Generate an AI response based on conversation history"""
        try:
            if ai_settings.ai_provider == "openai":
                return await self._generate_openai_response(
                    ai_settings, conversation_history, participant_name
                )
            elif ai_settings.ai_provider == "anthropic":
                return await self._generate_anthropic_response(
                    ai_settings, conversation_history, participant_name
                )
            else:
                logger.error(f"Unknown AI provider: {ai_settings.ai_provider}")
                return None
        except Exception as e:
            logger.error(f"Failed to generate AI response: {e}")
            return None

    async def _generate_openai_response(
        self,
        ai_settings: AISettings,
        conversation_history: List[Message],
        participant_name: str
    ) -> Optional[str]:
        """Generate response using OpenAI API"""
        if not ai_settings.api_key:
            logger.error("OpenAI API key not configured")
            return None

        # Build messages for OpenAI format
        messages = []

        # Add system prompt
        system_prompt = ai_settings.system_prompt or self._get_default_system_prompt(ai_settings.response_tone)
        messages.append({
            "role": "system",
            "content": system_prompt
        })

        # Add conversation history (limited by context_messages_count)
        recent_messages = conversation_history[-ai_settings.context_messages_count:]
        for msg in recent_messages:
            role = "assistant" if msg.direction == MessageDirection.OUTGOING else "user"
            content = msg.content or "[Media attachment]"
            messages.append({
                "role": role,
                "content": content
            })

        # Call OpenAI API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {ai_settings.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": ai_settings.model_name or "gpt-4",
                        "messages": messages,
                        "max_tokens": ai_settings.max_tokens,
                        "temperature": ai_settings.temperature / 10.0,  # Convert from 0-10 to 0-1
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"OpenAI API request failed: {e}")
            return None

    async def _generate_anthropic_response(
        self,
        ai_settings: AISettings,
        conversation_history: List[Message],
        participant_name: str
    ) -> Optional[str]:
        """Generate response using Anthropic (Claude) API"""
        if not ai_settings.api_key:
            logger.error("Anthropic API key not configured")
            return None

        # Build messages for Anthropic format
        messages = []

        # Add conversation history
        recent_messages = conversation_history[-ai_settings.context_messages_count:]
        for msg in recent_messages:
            role = "assistant" if msg.direction == MessageDirection.OUTGOING else "user"
            content = msg.content or "[Media attachment]"
            messages.append({
                "role": role,
                "content": content
            })

        # Get system prompt
        system_prompt = ai_settings.system_prompt or self._get_default_system_prompt(ai_settings.response_tone)

        # Call Anthropic API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ai_settings.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": ai_settings.model_name or "claude-3-sonnet-20240229",
                        "system": system_prompt,
                        "messages": messages,
                        "max_tokens": ai_settings.max_tokens,
                        "temperature": ai_settings.temperature / 10.0,
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["content"][0]["text"]
                else:
                    logger.error(f"Anthropic API error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Anthropic API request failed: {e}")
            return None

    def _get_default_system_prompt(self, tone: str) -> str:
        """Get default system prompt based on tone"""
        base_prompt = "You are a helpful AI assistant responding to customer messages."

        tone_additions = {
            "professional": " Maintain a professional and courteous tone. Be clear and concise.",
            "friendly": " Be warm, friendly, and approachable. Use casual language when appropriate.",
            "casual": " Be relaxed and conversational. Feel free to use informal language and show personality."
        }

        addition = tone_additions.get(tone, tone_additions["professional"])
        return base_prompt + addition
