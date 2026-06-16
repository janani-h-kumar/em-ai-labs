# EM-AI-LABS Architecture

## Purpose

EM-AI-LABS is an extensible local-first multi-agent orchestration harness.

The primary objective is not individual agents, but the orchestration framework that enables:

* Agent discovery
* Dependency injection
* Task planning
* Agent routing
* ReACT execution loops
* Memory integration
* Runtime abstraction
* Tool integration
* Observability

---

# High Level Architecture

User Goal

↓

AgentManager

↓

Orchestrator

↓

ReACTLoop

↓

Executor

↓

Router

↓

AgentRegistry

↓

AgentFactory

↓

Agents

---

# Component Responsibilities

## AgentManager

Application composition root.

Responsible for:

* Loading configuration
* Building ServiceContainer
* Initialising AgentRegistry
* Initialising Router
* Initialising Orchestrator

Owns the application lifecycle.

---

## ServiceContainer

Central dependency container.

Owns:

* ConfigManager
* Provider
* ToolRegistry

Infrastructure only.

Business logic must never depend directly on the container.

---

## AgentRegistry

Discovers agent implementations dynamically.

Responsibilities:

* Discover agent classes
* Register agents
* Provide agent lookup

Does not construct dependencies.

---

## AgentFactory

Constructs agent instances.

Responsibilities:

* Constructor introspection
* Dependency resolution
* Agent instantiation

Does not perform discovery.

---

## Router

Routes tasks to agents.

Current implementation:

* Keyword routing
* Regex routing

Future implementation:

* Capability routing
* Embedding routing
* Semantic routing

---

## Orchestrator

Coordinates execution lifecycle.

Responsibilities:

* Retrieve memory
* Create execution context
* Invoke ReACT loop
* Synthesize final response

---

## ReACTLoop

Implements:

Reason → Act → Observe → Respond

Responsibilities:

* Request plans
* Execute tasks
* Track completion
* Support iterative reasoning

---

## Planner

Converts goals into executable tasks.

Produces:

Task[]
TaskGraph

---

## Executor

Executes orchestration tasks.

Responsibilities:

* Resolve agent
* Invoke agent
* Update task status
* Support parallel execution

---

## Agents

Domain-specific capability providers.

Examples:

* WeatherAgent

Agents receive explicit dependencies.

Agents must never access the ServiceContainer.

---

# Dependency Flow

AgentManager
→ ServiceContainer
→ AgentRegistry
→ AgentFactory
→ Agent

Container ownership stops at infrastructure layers.

Agents receive only explicit dependencies.

---

# Future Roadmap

Phase 1

* Stable orchestration harness
* Dynamic discovery
* ReACT loop
* Memory abstraction

Phase 2

* Multi-agent execution
* Semantic routing
* Tool execution graph

Phase 3

* Autonomous planning
* Long-term memory
* Human-in-the-loop workflows
