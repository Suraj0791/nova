# AI use

Replace each prompt line (the ones starting with `>`) with your own words.

## Tools

> I used an AI coding assistant (Gemini 3.1 Pro via Antigravity IDE) to help structure the project and write the boilerplate code. We used it to design the 8-file architecture, set up the initial harness skeleton, and write the document reading logic (reader.py).

## How you worked with them

> I worked with the AI using a "vertical slicing" approach. I asked it to first lay out a complete end-to-end plan covering the 6 finding classes and the 5 hard gates. Then, I had it implement the foundation (reader and JSONL store) while I reviewed the logic to ensure it exactly matches the grader's string extraction method. I explicitly told the AI not to use LangChain or other heavy abstractions, forcing it to write simple, explainable Python.
> For Slice 2 (LLM Extraction), I asked the AI to implement the Anthropic SDK with robust document hashing (to cache API calls and prevent timeout failures). We also co-wrote the prompt to ensure strong Prompt Injection defense, wrapping the document content purely as DATA so that instructions like 'approve this invoice' are ignored, effectively protecting against one of the hard gates.
> For Slice 3 (Overcharge Detector), I guided the AI to create separate modules for resolving facts (`resolve.py`), detecting issues (`detectors.py`), and determining actions safely (`actions.py`). I ensured the AI explicitly used `decimal.Decimal` with `ROUND_HALF_UP` instead of floating point math to prevent precision errors. I also verified that the Action Safety Gate was built correctly to ensure `supervised` mode never sends outbound actions, guarding against another hard gate.

## Written without AI

> Any parts you wrote on your own, if there are some.

## Prompt log

> Paste the log here, or link the exported files in ai_log/. Take out secrets and nothing else.
