sample = """
╔══════════════════════════════════════════════════════════════╗
║         Token Tracker Chat — gemini-2.5-flash                ║
║  Context window: 1,048,576 tokens  |  type 'quit' to exit    ║
╚══════════════════════════════════════════════════════════════╝

You: What should I prepare for a Wipro fresher interview?

Gemini: Great question! Here's what to focus on for Wipro:

  📋 ROUNDS:
     1. Online Test — Aptitude, Logical Reasoning, Coding (1-2 Qs)
     2. Technical Interview — DSA, OOP, SQL, your projects
     3. HR Interview — communication, attitude, company fit

  💻 TECHNICAL TOPICS:
     • Data Structures: Arrays, Linked Lists, Trees, Stacks
     • OOP concepts: Inheritance, Polymorphism, Encapsulation
     • SQL: Basic queries, joins, normalization
     • Language: Pick ONE (Java/Python/C++) and know it well

  🎯 TIP: Wipro values communication as much as coding.
          Practice explaining your thought process out loud.

  ┌─────────────────────────────────────────────────────────┐
  │ turn 1 │ in: 42 tokens │ out: 187 tokens               │
  │ cost: $0.00012  │ session total: $0.00012               │
  │ context used: 0.004%  ░░░░░░░░░░░░░░░░░░░░░░           │
  └─────────────────────────────────────────────────────────┘

You: What about the HR round specifically?

Gemini: The HR round at Wipro is fairly standard but important...

  [answer here]

  ┌─────────────────────────────────────────────────────────┐
  │ turn 2 │ in: 241 tokens │ out: 203 tokens              │
  │ cost: $0.00016  │ session total: $0.00028               │
  │ context used: 0.023%  ░░░░░░░░░░░░░░░░░░░░░░           │
  └─────────────────────────────────────────────────────────┘

  NOTE: 'in' tokens grew from 42 → 241 because the full
  conversation history is sent every turn. That IS the memory.

You: quit

── Session Summary ──────────────────────────────────────────
  Turns completed : 2
  Total tokens    : 673
  Total cost      : $0.00028
  Avg cost/turn   : $0.00014
─────────────────────────────────────────────────────────────
"""
print(sample)
