# FAULTLINE ZERO — Security Architecture & Execution Boundaries

## Overview
FAULTLINE ZERO executes dynamic code comparisons and autonomous model reasoning. To prevent unauthorized access, remote code execution (RCE), prompt injection escalation, and credential exposure, the system enforces multi-layered defense-in-depth boundaries.

---

## 1. Execution Sandbox & Subprocess Isolation

> [!CAUTION]  
> A standard Python subprocess is **not a security sandbox**.

To prevent untrusted code from compromising host infrastructure:
1. **Container Read-Only Root Filesystem**:
   - The production Docker container runs with `read_only: true`.
   - Modifying system binaries, libraries, or installing unauthorized packages at runtime is physically blocked by the Linux kernel.
   - Temporary file writes are restricted to memory-backed `tmpfs` mounts (`/tmp`).
2. **Non-Root User Execution**:
   - The API service runs as an unprivileged user (`UID 1000:GID 1000`), preventing kernel-level privilege escalation.
3. **Execution Subprocess Timeouts**:
   - Subprocesses are executed using `subprocess.run` with a hard 8-second timeout (`SIGKILL` dispatched upon expiration).
4. **Stripped Environment**:
   - Child execution processes receive an explicitly sanitized `env` dictionary.
   - `GROQ_API_KEY`, `GITHUB_TOKEN`, database passwords, and internal URLs are completely stripped from the subprocess environment.

---

## 2. Agent Prompt Injection Defense

Autonomous tool-calling agents are vulnerable to indirect prompt injection if untrusted code or git diffs attempt to manipulate model instructions.

### Defenses Implemented:
1. **Strict Separation of Data and Instructions**:
   - Unified git diffs, commit messages, and AST symbol signatures are passed strictly as **Tool Observations**, never as system prompts or behavioral instructions.
2. **Schema-Constrained Tool Parameters**:
   - All tool arguments are validated against rigid Pydantic JSON schemas (`extra="forbid"`).
   - Arbitrary shell commands, Python scripts, or raw Cypher queries are strictly rejected by the validator.
3. **Deterministic Verdict Derivation**:
   - The LLM cannot simply declare "This code passes" or "This code failed".
   - The final deployment gate verdict is computed exclusively by the Python Differential Invariant Oracle:
     $$\text{Verdict} = (\text{baseline\_status} == \text{PASS} \land \text{candidate\_status} == \text{FAIL}) \implies \text{REPRODUCED}$$

---

## 3. Knowledge Graph (FalkorDB) Security

1. **Prewritten, Parameterized Cypher Queries**:
   - All Cypher queries use parameterized inputs (`$candidate_sha`, `$symbol_name`, `$invariant_id`).
   - Dynamic Cypher string concatenation from user input is strictly prohibited to prevent Cypher injection attacks.
2. **Local Loopback Network Binding**:
   - In Docker Compose, the FalkorDB port (`6379`) is bound to `127.0.0.1` (loopback only) and is not exposed to the public internet.

---

## 4. Credential & Secret Management

1. **Server-Side Only Credentials**:
   - `GROQ_API_KEY` and other sensitive provider keys are stored server-side via environment variables (`.env`).
   - Keys are never transmitted to the frontend client, never returned in API payloads, and never logged to stdout/stderr.
2. **API Bearer Authentication**:
   - Optional API bearer token verification protects administrative endpoints in multi-user environments.
