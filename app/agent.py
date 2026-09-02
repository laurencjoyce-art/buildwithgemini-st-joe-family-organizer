# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import uuid
from zoneinfo import ZoneInfo

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types


MODEL = "gemini-3.6-flash"

# Hardcode project ID and bucket name as strings for Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-bfc93a8a4c23"
FIRESTORE_COLLECTION = "family_events"
GCS_BUCKET_NAME = "bwg3-qwiklabs-gcp-03-bfc93a8a4c23"
CORPUS_NAME = "projects/112135878716/locations/us-central1/ragCorpora/2019890821154734080"


def generate_family_item_image(prompt: str, tool_context: ToolContext = None) -> str:
    """Generates an image for an item in the Saint Joseph family organizer domain (e.g. toddler hidden-veggie recipes, preschool activities, or St. Joseph beach/community events) using the gemini-3.1-flash-lite-image model in the global region.

    Args:
        prompt: Detailed description of the image to generate.
        tool_context: ToolContext supplied automatically by ADK to save artifacts.

    Returns:
        The public HTTPS URL of the generated image uploaded to Google Cloud Storage.
    """
    try:
        client = genai.Client(
            vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
        )
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        image_bytes = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return "Error: Image generation model did not return image bytes."

        filename = f"family_item_{uuid.uuid4().hex[:8]}.jpg"

        # 1. Save artifact for Playground Artifacts panel if tool_context is provided
        if tool_context:
            artifact_part = types.Part.from_bytes(
                data=image_bytes, mime_type="image/jpeg"
            )
            tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes to public Cloud Storage bucket
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Error generating or uploading image: {e}"


def consult_herbal_corpus(query: str) -> str:
    """Search Culpeper's Herbal corpus for botanical facts, plant remedies, or historical health uses.

    Args:
        query: What to look up (a plant, herb, ailment, or remedy).

    Returns:
        The matched passages from Culpeper's Herbal, or a notice if no relevant passage was found.
    """
    import vertexai
    from vertexai.preview import rag

    try:
        vertexai.init(project=FIRESTORE_PROJECT_ID, location="us-central1")
        resp = rag.retrieval_query(
            text=query,
            rag_resources=[rag.RagResource(rag_corpus=CORPUS_NAME)],
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=5),
        )
        contexts = getattr(resp.contexts, "contexts", [])
        passages = [c.text.strip() for c in contexts if getattr(c, "text", "").strip()]
        if not passages:
            return f"No relevant passage found in Culpeper's Herbal for query: '{query}'."
        return f"Passages from Culpeper's Herbal for '{query}':\n\n" + "\n\n---\n\n".join(passages)
    except Exception as e:
        return f"Retrieval from Culpeper's Herbal failed: {e}"


def get_firestore_client() -> firestore.Client:
    """Helper to initialize Firestore client with hardcoded project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def list_family_events(category: str = "") -> str:
    """Reads family events and preschool notices from the Firestore database.

    Args:
        category: Optional category to filter events by (e.g., 'preschool', 'family', 'medical').
                  Leave empty to retrieve all scheduled family events.

    Returns:
        A string formatted list of matching family events.
    """
    try:
        db = get_firestore_client()
        docs_ref = db.collection(FIRESTORE_COLLECTION)

        if category:
            query = docs_ref.where("category", "==", category.lower().strip())
            docs = query.stream()
        else:
            docs = docs_ref.stream()

        events = []
        for doc in docs:
            data = doc.to_dict()
            events.append(
                f"• [{data.get('date', 'N/A')}] {data.get('title')} ({data.get('category', 'general')})\n"
                f"  Details: {data.get('details', '')}"
            )

        if not events:
            return f"No family events found in Firestore for category '{category}'."
        return "Family Events & Notices from Firestore:\n" + "\n\n".join(events)
    except Exception as e:
        return f"Error reading events from Firestore: {e}"


def add_family_event(title: str, date: str, category: str, details: str) -> str:
    """Adds a new family event or school notice into the Firestore database.

    Args:
        title: Title of the event or school notice (e.g. 'Piper Music Class').
        date: Date of the event in YYYY-MM-DD format.
        category: Category of the event (e.g. 'preschool', 'family', 'medical').
        details: Additional notes or instructions for the event.

    Returns:
        Confirmation message that the event was saved to Firestore.
    """
    try:
        db = get_firestore_client()
        doc_ref = db.collection(FIRESTORE_COLLECTION).document()
        doc_data = {
            "title": title,
            "date": date,
            "category": category.lower().strip(),
            "details": details,
            "completed": False,
        }
        doc_ref.set(doc_data)
        return f"Successfully saved event '{title}' scheduled for {date} to Firestore (Doc ID: {doc_ref.id})."
    except Exception as e:
        return f"Error adding event to Firestore: {e}"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    elif "st. joseph" in query.lower() or "saint joseph" in query.lower() or "st joseph" in query.lower():
        return "Saint Joseph, MI: 72 degrees and partly cloudy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    elif "st. joseph" in query.lower() or "saint joseph" in query.lower() or "st joseph" in query.lower() or "michigan" in query.lower():
        tz_identifier = "America/Detroit"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: Send the session events to Vertex AI Memory Bank for extraction after each turn."""
    await callback_context.add_session_to_memory()
    return None


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the Saint Joseph Family & Meal Organizer assistant. "
        "You help manage family schedules and preschool notices using your Firestore database tools (list_family_events, add_family_event), "
        "answer botanical or herbal questions grounded in Culpeper's Herbal using your retrieval tool (consult_herbal_corpus), "
        "generate visual images for family recipes, toddler meals, or St. Joseph activities using your image tool (generate_family_item_image), "
        "toddler-friendly meal plans (with hidden veggies for 3yo Piper), "
        "next-day weather/clothing prep in Saint Joseph, Michigan, and grocery deals. "
        "You remember the user's stated preferences, family details, and facts from previous conversations "
        "using your long-term memory to personalize all responses."
    ),
    tools=[
        PreloadMemoryTool(),
        list_family_events,
        add_family_event,
        consult_herbal_corpus,
        generate_family_item_image,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)

