## Agent Lifecycle and State

Agents are long-lived service objects.

Agents MUST be stateless.

Allowed:

- provider references
- tool references
- configuration
- prompts/templates

Not allowed:

- current_user
- session_id
- conversation history
- last_response
- task results
- request-specific data

All request state belongs in ExecutionContext.

All conversation state belongs in Memory.