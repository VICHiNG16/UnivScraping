# Directives

This folder contains the **Layer 1: Directive** files of the agent architecture.

## What is a Directive?
A directive is a Standard Operating Procedure (SOP) written in Markdown. It defines the "What/Why/How" of a specific business goal.

## Format
Directives should generally include:
1.  **Goal**: What are we trying to achieve?
2.  **Input**: What data or triggers start this process?
3.  **Output**: What is the final deliverable?
4.  **Instructions**: Step-by-step natural language instructions.
5.  **Tools/Scripts**: References to the specific Python scripts in `../execution/` that should be run.
6.  **Edge Cases**: How to handle common errors.

## Workflow
1.  Agent reads a Directive.
2.  Agent orchestrates the execution by running scripts in `../execution/`.
3.  Agent updates the Directive if it learns new constraints or optimizations.
