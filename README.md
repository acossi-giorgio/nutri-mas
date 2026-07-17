# Nutri-MAS

Academic **Multi-Agent Systems** project developed in **2026**.

This repository contains a conversational assistant for personalized nutritional support.  
The application combines **reactive**, **BDI**, and **LLM-based agents** to collect a user profile, calculate nutritional targets, generate a weekly meal plan, create recipes, track consumed meals, and rebalance the remaining plan when the user deviates from it.

## Project

- **Project name:** Nutri-MAS
- **Full title:** Nutri-MAS: a hybrid multi-agent system for personalized nutritional assistance
- **Scope:** academic project on autonomous intelligent and multi-agent systems
- **Year:** 2026
- **Author:** Giorgio Roberto Acossi

## Objective

The project explores how agents with different decision-making models can collaborate in a single application:

1. a reactive Gateway manages the interaction with the user
2. an LLM-based NLP Agent translates natural language into structured AgentSpeak commands
3. BDI agents manage the user profile, nutritional rules, planning, and meal templates
4. an LLM-based Creative Cook generates recipes and evaluates freely described meals
5. the system records the results and rebalances future meals when necessary

The main goal is not only to generate meal plans, but also to maintain a consistent nutritional state through explicit beliefs, rules, inter-agent communication, and persistent data.

## Main Features

- conversational onboarding and user profile management
- indicative calorie and macronutrient target calculation
- weekly meal-plan generation
- recipe generation based on nutritional and dietary constraints
- support for diet types, allergens, and culinary preferences
- meal and weight tracking
- evaluation of off-plan meals described in natural language
- automatic rebalancing of subsequent meals
- proactive meal monitoring and confirmation
- consultation of daily plans, weekly plans, summaries, and history
- accelerated simulation clock for demo purposes

## Architecture

Nutri-MAS uses six specialized agents:

- **Gateway Agent — reactive**
  - connects the Streamlit interface to the multi-agent system
  - validates commands and routes messages

- **NLP Agent — LLM**
  - interprets natural-language requests
  - retrieves message templates through semantic search
  - produces validated AgentSpeak-compatible commands

- **Nutritionist Agent — BDI**
  - manages the user profile, nutritional targets, weight history, and meal log
  - monitors daily progress and coordinates plan rebalancing

- **Planner Agent — BDI**
  - builds and updates the weekly meal plan
  - applies variety, frequency, diet, and slot constraints

- **Chef Agent — BDI**
  - selects abstract meal templates that satisfy the planner's constraints

- **Creative Cook Agent — LLM**
  - turns meal templates into complete recipes
  - searches the ingredient database and estimates freely described meals

Agents communicate through **XMPP** using messages whose content follows an **AgentSpeak-compatible** representation. The application embeds its local XMPP server, so no separate XMPP installation is required.

## Tech Stack

- **Application and UI**
  - Python
  - Streamlit

- **Multi-agent system**
  - SPADE
  - SPADE-BDI
  - SPADE-LLM
  - AgentSpeak
  - XMPP / pyjabber

- **LLM and semantic search**
  - LiteLLM Proxy
  - Azure OpenAI configuration
  - Qdrant

- **Persistence and data processing**
  - CSV
  - pandas
  - openpyxl

## Local Setup

### Requirements

- Python
- PowerShell
- access to compatible chat and embedding model deployments

### Create the environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Configure the application

Create the local configuration files from the provided examples:

```powershell
Copy-Item config\.env.example config\.env
Copy-Item config\litellm_config.example.yaml config\litellm_config.yaml
```

Then edit both files:

- `config/.env`
  - set the Azure OpenAI endpoint, API key, and API version
  - configure the chat and embedding model aliases
  - optionally change the username, timezone, or simulation speed

- `config/litellm_config.yaml`
  - replace the example chat deployment name
  - replace the example embedding deployment name

The local configuration files may contain credentials and are excluded from version control.

### Run the application

Start the complete system with:

```powershell
.\scripts\run.ps1
```

The script:

- loads the local environment configuration
- starts a LiteLLM Proxy on port `4000` when one is not already available
- waits for the proxy to become ready
- launches the Streamlit application
- stops the proxy it created when the application closes

Streamlit normally exposes the interface at:

```text
http://localhost:8501
```

If a LiteLLM Proxy is already running, reuse it with:

```powershell
.\scripts\run.ps1 -SkipLiteLLM
```

## Configuration

The main environment variables are:

- `LITELLM_PROXY_BASE_URL`: LiteLLM Proxy address
- `LITELLM_PROXY_API_KEY`: local proxy key
- `LLM_MODEL`: alias of the chat model used by the agents
- `EMBEDDING_MODEL`: alias of the embedding model used by Qdrant indexing
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI resource endpoint
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_API_VERSION`: supported Azure OpenAI API version
- `NUTRIMAS_USERNAME`: application identity used by the agents
- `CLOCK_SPEED`: clock multiplier; values greater than `1` accelerate the demo
- `TIMEZONE`: application timezone, for example `Europe/Rome`

## Data Management

The project uses two complementary storage mechanisms:

- **CSV files** preserve the user profile, weight history, meal log, generated plan, meal templates, nutritional rules, and ingredient data.
- **Qdrant collections** provide semantic retrieval for natural-language message templates and ingredients.

The Qdrant collections are built locally at startup from the versioned project data. No external Qdrant server needs to be configured.

The files under `src/data/nutritionist/` and `src/data/planner/` contain persistent application state and can change while the system is running.

## Repository Structure

```text
.
├── config
│   ├── .env.example
│   └── litellm_config.example.yaml
├── report
│   ├── images
│   ├── report.pdf
│   └── report.tex
├── scripts
│   ├── import_afcd.py
│   └── run.ps1
├── src
│   ├── agents
│   │   ├── chef_agent.py
│   │   ├── creative_cook_agent.py
│   │   ├── gateway_agent.py
│   │   ├── nlp_agent.py
│   │   ├── nutritionist_agent.py
│   │   └── planner_agent.py
│   ├── bdi
│   │   ├── chef.asl
│   │   ├── nutritionist.asl
│   │   └── planner.asl
│   ├── data
│   │   ├── chef
│   │   ├── cook
│   │   ├── nutritionist
│   │   └── planner
│   ├── domain
│   ├── runtime
│   ├── ui
│   ├── utils
│   └── main.py
├── requirements.txt
└── README.md
```

### Folder Details

- `src/agents/`
  - contains the Python implementations of the reactive, BDI, and LLM-based agents

- `src/bdi/`
  - contains the AgentSpeak plans and rules used by the Nutritionist, Planner, and Chef agents

- `src/data/`
  - contains persistent state and the static datasets used by the agents

- `src/runtime/`
  - starts the embedded XMPP server and coordinates the lifecycle of all agents

- `src/ui/`
  - contains Streamlit state management, event handling, and message rendering

- `src/utils/`
  - contains messaging, persistence, Qdrant, LLM configuration, nutrition, logging, and time utilities

- `scripts/`
  - contains the PowerShell launcher and the ingredient dataset import utility

- `report/`
  - contains the complete technical report and demo images

## Documentation

The complete project report is available in [`report/report.pdf`](report/report.pdf). It describes the architecture, agent behaviours, communication protocols, data management, workflows, demo scenarios, and current limitations in detail.
