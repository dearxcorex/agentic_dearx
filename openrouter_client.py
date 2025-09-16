"""OpenRouter API Client with intelligent model selection"""

import httpx
import json
from typing import Dict, List, Optional, Any
from tenacity import retry, stop_after_attempt, wait_exponential
from cachetools import TTLCache
from config import Config, ModelConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenRouterClient:
    """OpenRouter API client with cost-optimized model selection"""

    def __init__(self):
        self.api_key = Config.OPENROUTER_API_KEY
        self.base_url = Config.OPENROUTER_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/fm-station-planner",
            "X-Title": "FM Station Inspection Planner"
        }
        # Cache for repeated queries
        self.cache = TTLCache(maxsize=100, ttl=Config.CACHE_TTL_SECONDS)
        self.total_cost = 0.0

    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(min=1, max=10)
    )
    def _make_request(self,
                     messages: List[Dict[str, str]],
                     model_config: ModelConfig,
                     **kwargs) -> Dict[str, Any]:
        """Make API request to OpenRouter"""

        payload = {
            "model": model_config.name,
            "messages": messages,
            "max_tokens": model_config.max_tokens,
            "temperature": model_config.temperature,
            **kwargs
        }

        cache_key = f"{model_config.name}:{json.dumps(messages)}"

        # Check cache first
        if cache_key in self.cache:
            logger.info(f"Cache hit for {model_config.name}")
            return self.cache[cache_key]

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=Config.MAX_RESPONSE_TIME_SECONDS
                )
                response.raise_for_status()
                result = response.json()

                # Calculate and track costs
                usage = result.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                input_cost = (input_tokens / 1000) * model_config.cost_per_1k_input
                output_cost = (output_tokens / 1000) * model_config.cost_per_1k_output
                request_cost = input_cost + output_cost

                self.total_cost += request_cost

                logger.info(f"Model: {model_config.name}, Cost: ${request_cost:.6f}, "
                          f"Total: ${self.total_cost:.6f}")

                # Cache successful response
                self.cache[cache_key] = result

                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            # Try fallback to cheaper model
            if model_config.name != Config.MODELS["simple_tasks"].name:
                logger.info("Falling back to cheaper model")
                return self._make_request(
                    messages,
                    Config.MODELS["simple_tasks"],
                    **kwargs
                )
            raise

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    def complete(self,
                prompt: str,
                task_type: str = "simple_tasks",
                system_prompt: Optional[str] = None) -> str:
        """Get completion from appropriate model based on task type"""

        model_config = Config.get_model(task_type)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = self._make_request(messages, model_config)

        return result["choices"][0]["message"]["content"]

    def parse_location(self, text: str) -> Dict[str, Any]:
        """Parse Thai location text using specialized model"""

        system_prompt = """You are a Thai location parser. Extract location information from Thai text.
        Return ONLY a JSON object with these fields:
        - province: Thai province name
        - district: Thai district name (if mentioned)
        - subdistrict: Thai subdistrict name (if mentioned)
        - landmarks: List of landmarks mentioned

        Example response:
        {"province": "ชัยภูมิ", "district": null, "subdistrict": null, "landmarks": []}"""

        prompt = f"Extract location from: {text}"

        response = self.complete(
            prompt,
            task_type="location_parsing",
            system_prompt=system_prompt
        )

        try:
            # Clean response and parse JSON
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            return json.loads(json_str)
        except:
            # Fallback parsing
            return {"province": text, "district": None, "subdistrict": None, "landmarks": []}

    def generate_thai_response(self,
                               stations: List[Dict],
                               route_info: Dict,
                               user_requirements: str) -> str:
        """Generate natural Thai language response"""

        system_prompt = """You are a helpful Thai assistant for FM station inspection planning.
        Generate clear, natural Thai responses with numbered station lists.
        Include distance, travel time, and total time information.
        Be concise but informative."""

        prompt = f"""User requirements: {user_requirements}

Stations found: {json.dumps(stations, ensure_ascii=False, indent=2)}
Route information: {json.dumps(route_info, ensure_ascii=False, indent=2)}

Generate a Thai response with:
1. Numbered list of stations
2. Distance from previous station
3. Travel time between stations
4. Total time (travel + 10 min inspection per station)
5. Summary at the end"""

        return self.complete(
            prompt,
            task_type="thai_language",
            system_prompt=system_prompt
        )

    def generate_english_response(self,
                                 stations: List[Dict],
                                 route_info: Dict,
                                 user_requirements: str) -> str:
        """Generate natural English language response"""
        system_prompt = """You are a helpful assistant for FM station inspection planning.
        Generate clear, natural English responses with numbered station lists.
        Include distance, travel time, and total time information.
        Be concise but informative."""

        prompt = f"""User requirements: {user_requirements}
Stations found: {json.dumps(stations, ensure_ascii=False, indent=2)}
Route information: {json.dumps(route_info, ensure_ascii=False, indent=2)}

Generate an English response with:
1. Numbered list of stations
2. Distance from previous station
3. Travel time between stations
4. Total time (travel + 10 min inspection per station)
5. Summary at the end"""

        return self.complete(
            prompt,
            task_type="thai_language",  # Use same model but with English prompt
            system_prompt=system_prompt
        )

    def optimize_route_with_ai(self,
                               stations: List[Dict],
                               constraints: Dict) -> List[int]:
        """Use AI to suggest route optimizations"""

        system_prompt = """You are a route optimization expert.
        Given stations with coordinates and constraints, suggest the optimal visiting order.
        Consider: total time, distance, and inspection requirements.
        Return ONLY a JSON array of station indices in optimal order."""

        prompt = f"""Optimize route for these stations:
{json.dumps(stations, ensure_ascii=False, indent=2)}

Constraints:
- Max time: {constraints.get('max_time_minutes')} minutes
- Inspection time per station: 10 minutes
- Starting location: {constraints.get('start_location')}

Return optimal order as JSON array of indices."""

        response = self.complete(
            prompt,
            task_type="complex_reasoning",
            system_prompt=system_prompt
        )

        try:
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1].replace("json", "").strip()
            return json.loads(json_str)
        except:
            # Fallback to sequential order
            return list(range(len(stations)))

    def get_total_cost(self) -> float:
        """Get total API costs for this session"""
        return self.total_cost