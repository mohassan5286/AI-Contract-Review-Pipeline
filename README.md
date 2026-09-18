# AI Contract Review Pipeline

A distributed, fault-tolerant AI pipeline designed exclusively for legal contract review. Built with FastAPI and the Temporal Python SDK, this system synthesizes cross-contract risks using LLMs and incorporates a stateful Human-in-the-Loop (HITL) revision cycle.

## Prerequisites

* Docker & Docker Compose
* Python 3.11+

## Getting Started

### 1. Start the Infrastructure

Start the required database and Temporal server in the background:

```bash
cd "setup/samples-server/compose"
docker compose -f docker-compose-postgres.yml up -d

```

> **Note:** If the default namespace fails to initialize automatically, install the Temporal CLI and create it manually:

```bash
temporal operator namespace create -n default

```

### 2. Set Up the Environment

Create your Conda environment and install the required dependencies. Because the architecture separates the Temporal worker from the FastAPI client, you must install dependencies and configure environment variables in both directories.

```bash
# Create and activate the Conda environment
conda create -n temporal-ai python=3.11 -y
conda activate temporal-ai

# Set up the worker environment
cd app/ai-contract-review
pip install -r requirements.txt
cp .env.example .env

# Set up the client environment
cd ../client-app
pip install -r requirements.txt
cp .env.example .env

```
Configure both newly created `.env` files with your values


### 3. Run the Application

Run the worker and the API server in two separate terminal windows.

**Terminal 1 (The Worker):** Runs the Temporal worker that listens for tasks and executes workflow activities.

```bash
cd app/ai-contract-review
python worker.py

```

**Terminal 2 (The API):** Starts the FastAPI server (`main.py`) to accept HTTP client requests and interact with Temporal.

```bash
cd app/client-app
uvicorn main:app --reload --port 8000

```

### 4. Monitor the Workflows (Temporal Web UI)

The Docker infrastructure automatically launches the Temporal Web UI. Use this dashboard to monitor workflow progress, inspect AI payloads, and track Human-in-the-Loop interactions in real time.

* **Dashboard URL:** [http://localhost:8080](http://localhost:8080?utm_source=gemini)
* **Namespace:** `default`

---

## API Reference

### Contract Review Lifecycle

#### 1. Start Review

Initiates a new parent workflow that runs child extraction workflows in parallel.

* **Method:** `POST`
* **Endpoint:** `/contract-review/start`
* **Request Body:**

```json
{
  "s3_paths": [
    "s3://my-bucket/contract-1.pdf",
    "s3://my-bucket/contract-2.pdf",
    "s3://my-bucket/contract-3.pdf"
  ],
  "max_revisions": 2
}

```

---

#### 2. Get Status

Queries the real-time execution status and an excerpt preview of the report.

* **Method:** `GET`
* **Endpoint:** `/contract-review/{workflow_id}/status`

---

#### 3. Assign Reviewer

Sends a Temporal Signal to assign a human reviewer without interrupting the workflow's state.

* **Method:** `POST`
* **Endpoint:** `/contract-review/assign-reviewer`
* **Request Body:**

```json
{
  "workflow_id": "workflow-id",
  "name": "Reviewer Name"
}

```

---

#### 4. Get Report

Queries the full, parsed JSON synthesis report across all contracts.

* **Method:** `GET`
* **Endpoint:** `/contract-review/{workflow_id}/report`

---

#### 5. Request Revision

Sends a Temporal Update containing human feedback, triggering a new synthesis step to refine the report.

* **Method:** `POST`
* **Endpoint:** `/contract-review/revise`
* **Request Body:**

```json
{
  "workflow_id": "workflow-id",
  "feedback": "feedback-notes"
}

```

---

#### 6. Approve Report

Sends a Temporal Update to approve the final report, completing the Human-in-the-Loop cycle and closing the workflow.

* **Method:** `POST`
* **Endpoint:** `/contract-review/approve`
* **Request Body:**

```json
{
  "workflow_id": "workflow-id"
}

```
