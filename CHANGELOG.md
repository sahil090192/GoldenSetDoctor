# Golden-Set Doctor: Applied Fixes

- Source dataset: `examples/office_eval/dataset_office40.jsonl`

- Output dataset: `examples/office_eval/dataset_office40_v2.jsonl`

## Duplicate merges

- Kept `O27` as canonical; merged members: `O01`, `O02`. Appended members' expected/accepted to canonical `accepted`.
- Kept `O06` as canonical; merged members: `O05`. Appended members' expected/accepted to canonical `accepted`.

## Leakage marked as open-book

- `O08`: set `context_url` to `examples/office_eval/refs/word_page_numbers.txt`
- `O15`: set `context_url` to `examples/office_eval/refs/outlook_delay_delivery.txt`
- `O16`: set `context_url` to `examples/office_eval/refs/onedrive_retention.txt`
- `O24`: set `context_url` to `examples/office_eval/refs/outlook_delay_delivery.txt`
- `O25`: set `context_url` to `examples/office_eval/refs/onedrive_retention.txt`
- `O26`: set `context_url` to `examples/office_eval/refs/excel_shortcuts.txt`

## Rubric issues (manual action suggested)

- Errors: **5**, Warnings: **4**

  - `O23` [warn:ambiguous_llm]: LLM flagged missing scope or vague phrasing.  
    Suggest: Clarify by specifying the application (e.g., Word, PowerPoint, Windows) and the context (e.g., document, slide master, OS).
  - `O23` [error:not_gradeable]: LLM judged the expected answer not sufficiently objective to grade.  
    Suggest: Clarify by specifying the application (e.g., Word, PowerPoint, Windows) and the context (e.g., document, slide master, OS).
  - `O24` [error:missing_expected]: Expected answer is missing or empty.  
    Suggest: Add a concise, objective expected answer.
  - `O24` [warn:ambiguous_llm]: LLM flagged missing scope or vague phrasing.  
    Suggest: Specify the software or context for exporting to PDF and provide an expected outcome or criteria for evaluation.
  - `O24` [error:not_gradeable]: LLM judged the expected answer not sufficiently objective to grade.  
    Suggest: Specify the software or context for exporting to PDF and provide an expected outcome or criteria for evaluation.
  - `O25` [warn:too_short]: Expected answer is very short (1 words).  
    Suggest: Add minimal steps or criteria to make it gradeable.
  - `O25` [error:not_gradeable]: LLM judged the expected answer not sufficiently objective to grade.  
    Suggest: Provide detailed steps on how to turn on dark mode in a specific version of Office.
  - `O26` [warn:too_short]: Expected answer is very short (5 words).  
    Suggest: Add minimal steps or criteria to make it gradeable.
  - `O28` [error:multi_intent_signals]: Question likely asks for multiple actions.  
    Suggest: Split into separate, single-task items.
