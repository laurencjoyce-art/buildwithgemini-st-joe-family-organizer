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

"""Seed script to populate Firestore with initial family events and school notices."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-bfc93a8a4c23"
COLLECTION_NAME = "family_events"

SEED_EVENTS = [
    {
        "id": "event_001",
        "title": "Piper Preschool Finger Painting & Art Day",
        "date": "2026-09-03",
        "category": "preschool",
        "details": "Send Piper in paint-friendly clothes and pack a spare outfit in her backpack.",
        "completed": False,
    },
    {
        "id": "event_002",
        "title": "St. Joe Farmers Market",
        "date": "2026-09-05",
        "category": "community_toddler",
        "details": "Saturdays 9:00am - 2:00pm in Lake Bluff Park overlooking Lake Michigan. Fresh fruit, baked goods, and stroller-friendly walking.",
        "completed": False,
    },
    {
        "id": "event_003",
        "title": "Piper 3-Year Pediatrician Wellness Visit",
        "date": "2026-09-10",
        "category": "medical",
        "details": "Bring growth chart and immunization record to Dr. Smith's office in St. Joseph.",
        "completed": False,
    },
    {
        "id": "event_004",
        "title": "St. Joe Movies in the Park (Whirlpool Centennial Park)",
        "date": "2026-09-04",
        "category": "community_toddler",
        "details": "Free family movie screening at dusk at Whirlpool Centennial Park (200 Broad St). Bring blankets, lawn chairs, and snacks for Piper.",
        "completed": False,
    },
    {
        "id": "event_005",
        "title": "Wednesday Brown Bag Concert Series",
        "date": "2026-09-02",
        "category": "community_toddler",
        "details": "Wednesdays 12:00pm - 1:00pm at John E.N. Howard Bandshell. Outdoor family picnic concert overlooking St. Joseph River.",
        "completed": False,
    },
    {
        "id": "event_006",
        "title": "Friday Night Concert Series",
        "date": "2026-09-04",
        "category": "community_toddler",
        "details": "Fridays 7:00pm - 8:00pm at John E.N. Howard Bandshell. Sunset music by the river, toddler-friendly dancing and fresh air.",
        "completed": False,
    },
    {
        "id": "event_007",
        "title": "St. Joe Lighthouse Tours & Pier Walk",
        "date": "2026-09-05",
        "category": "community_toddler",
        "details": "Saturdays 10:00am - 7:00pm at North Pier / Tiscornia Park. Explore free 1st-floor exhibits and watch boats on Lake Michigan.",
        "completed": False,
    },
]


def main():
    db = firestore.Client(project=PROJECT_ID)
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")

    collection_ref = db.collection(COLLECTION_NAME)

    for item in SEED_EVENTS:
        doc_id = item.pop("id")
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"Seeded document '{doc_id}': {item['title']}")

    print("Firestore seeding complete!")


if __name__ == "__main__":
    main()
