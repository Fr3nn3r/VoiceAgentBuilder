# Airtable MVP Schema Summary

This document summarizes the three connected tables in your Airtable base for Dr. Fillion’s assistant (Camille/Ava voice agents). The goal is to let developers understand the schema, relationships, and automation integration points.

---

## 1. Conversations

**Purpose:** Logs every interaction between the AI voice agent (e.g., Ava) and a patient. Includes the call transcript, audio, and extracted summary/sentiment.

### Key Fields

| Field                           | Type                                | Description                                                                   |
| ------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------- |
| **Voice Agent Name**            | Single select                       | Name of the voice agent handling the call (e.g., Ava, Camille).               |
| **Audio Recording**             | Attachment                          | Audio file of the conversation; playable directly in Airtable.                |
| **Transcript**                  | Long text                           | Full transcription of the call.                                               |
| **Conversation Date**           | Date                                | Date of the call or conversation.                                             |
| **Patient**                     | Linked record → `Patients`          | Links the conversation to a patient.                                          |
| **Appointment**                 | Linked record → `Appointments`      | Links the conversation to the related appointment.                            |
| **Conversation Outcome**        | Single select                       | E.g., Booked / Rescheduled / Cancelled.                                       |
| **Appointment Status**          | Single select                       | Mirrors status in the `Appointments` table (Scheduled, Completed, Cancelled). |
| **Patient Name**                | Lookup                              | Patient name from linked record.                                              |
| **Appointment Date**            | Lookup                              | Appointment date from linked record.                                          |
| **Conversation Summary (AI)**   | Long text (formula or AI-generated) | Short summary of what happened in the call.                                   |
| **Conversation Sentiment (AI)** | Single select (AI-generated)        | Positive / Neutral / Negative.                                                |

### Relationships

* One **Patient** → Many **Conversations**
* One **Appointment** → One **Conversation** (usually)

### Integration Notes

* **Inbound data from LiveKit/n8n:** Transcript + audio URL are inserted automatically.
* **AI enrichment:** Conversation summary and sentiment can be auto-generated via OpenAI or Airtable AI extension.
* **Doctor UI:** Dr. Fillion can read transcripts and play audio directly from Airtable.

---

## 2. Patients

**Purpose:** Central directory of patients with personal info, linked conversations, and appointments.

### Key Fields

| Field                      | Type                            | Description                                                       |
| -------------------------- | ------------------------------- | ----------------------------------------------------------------- |
| **Full Name**              | Text                            | Patient’s full name.                                              |
| **Date of Birth**          | Date                            | Used for identification and age calculations.                     |
| **Phone Number**           | Phone                           | Contact number used for calls.                                    |
| **Email Address**          | Email                           | Contact email.                                                    |
| **Profile Photo**          | Attachment                      | Optional profile image.                                           |
| **Appointments**           | Linked record → `Appointments`  | Shows the patient’s scheduled or past appointments.               |
| **Conversations**          | Linked record → `Conversations` | All calls or transcripts related to the patient.                  |
| **Total Appointments**     | Formula / count                 | Total number of linked appointments.                              |
| **Upcoming?**              | Formula / checkbox              | Indicates if the next appointment is in the future.               |
| **Last Appointment Date**  | Lookup                          | Most recent appointment date.                                     |
| **Last Conversation Date** | Lookup                          | Most recent call date.                                            |
| **Most Recent Transcript** | Lookup                          | Latest conversation text.                                         |
| **Patient Summary (AI)**   | Long text                       | Automatically generated summary (personality, reliability, etc.). |
| **Patient Sentiment (AI)** | Single select                   | Overall sentiment based on latest calls.                          |

### Relationships

* One **Patient** → Many **Appointments**
* One **Patient** → Many **Conversations**

### Integration Notes

* Each new patient can be auto-created when the first call comes in.
* Patient summaries and sentiment can be derived from conversation history (AI enrichment).
* Use this table as a CRM-like view for Dr. Fillion.

---

## 3. Appointments

**Purpose:** Manages scheduled, completed, or cancelled appointments and connects them to conversations.

### Key Fields

| Field                           | Type                            | Description                                 |
| ------------------------------- | ------------------------------- | ------------------------------------------- |
| **Appointment Time**            | Time                            | Scheduled appointment time.                 |
| **Appointment Date**            | Date                            | Scheduled date.                             |
| **Status**                      | Single select                   | Scheduled / Completed / Cancelled.          |
| **Patient**                     | Linked record → `Patients`      | The patient who owns the appointment.       |
| **Conversation**                | Linked record → `Conversations` | Related phone call or confirmation.         |
| **Booking Created At**          | Date                            | When the appointment was initially booked.  |
| **Notes**                       | Long text                       | Internal or patient-facing notes.           |
| **Conversation Transcript**     | Lookup                          | Transcript of the associated conversation.  |
| **Conversation Outcome**        | Lookup                          | E.g., Booked / Rescheduled / Cancelled.     |
| **Days Until Appointment**      | Formula                         | `Appointment Date - Today()` for reminders. |
| **Is Upcoming?**                | Formula                         | Boolean flag for upcoming appointments.     |
| **Appointment Summary (AI)**    | Long text                       | Generated summary for the doctor.           |
| **Conversation Sentiment (AI)** | Lookup                          | Pulls sentiment from related conversation.  |

### Relationships

* One **Patient** → Many **Appointments**
* One **Appointment** ↔ One **Conversation**

### Integration Notes

* Appointments can be created directly by the AI agent (via n8n → Airtable API).
* Use formulas to compute days remaining and highlight upcoming visits.
* Status should update automatically based on call intent.

---

## 🔗 Integration Overview (Automation Layer)

**Inbound (AI Agent → n8n → Airtable):**

* n8n webhook receives JSON from the voice agent with: transcript, recording link, appointment info, sentiment.
* n8n upserts:

  * **Conversation** record with transcript + audio URL.
  * **Appointment** record (new or existing).
  * **Patient** record (if missing).

**Outbound (Airtable → Doctor):**

* Dr Fillion reviews conversations directly in Airtable (audio playback + summary).
* Optional: daily digest email (via n8n) of new or updated calls.

---

### 🪶 Summary for Developers

* **3 linked tables:** `Patients`, `Appointments`, `Conversations`.
* **Relationships:** Patient ↔ Appointment ↔ Conversation (1-to-many / many-to-1).
* **Automation:** n8n webhook receives JSON, writes to Airtable via API.
* **AI fields:** Summary & Sentiment are post-processed (OpenAI or Airtable AI).
* **UX goal:** Dr Fillion can read, search, and listen to calls inside Airtable — no custom frontend required.
