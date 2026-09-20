# Pre-Thesis Presentation Script — 19 slides (17 timed + 2 backup)

**Project:** An LLM-powered Application for Detecting Academic Stress Levels in Vietnamese University Students
**Deck:** `report/PreThesis_Slides_v6_with_figures.pptx`
**Target length:** ~14 minutes speaking + up to 10 minutes Q&A
**Revised:** 2026-09-10 — rewritten to match the actual 19-slide deck (the earlier 15-slide script was stale: wrong slide numbers, wrong crisis-recall figures, wrong coverage percentage).

> **Language note.** Slide text and the spoken script are in English, matching
> `report/PreThesis_Report.md` and the English-medium programme. *Ghi chú* notes
> are Vietnamese rehearsal notes, not for the screen. A full Vietnamese briefing
> is at the end of this file.

> **Every number below was checked against `data/eval/*` on 2026-09-10** — 24
> claims cross-checked against source artefacts, all confirmed. If a number here
> ever disagrees with the deck, the deck is the one to trust; rebuild this file's
> numbers with `python -m app.eval.compare`, `python -m app.eval.crisis_eval`,
> `python -m app.eval.retrieval_eval`, `python -m app.eval.latency_eval`, and
> `python scripts/check_leakage.py`.

---

## Delivery strategy — read this first

**Volunteer the weaknesses before the panel extracts them.** Three findings are
genuinely unflattering — template-derived data, a crisis rule that used to miss
half its cases, and a proposed system with no reportable score. Said first, each
lands as rigour. Found by the panel, each lands as concealment.

Slides 5 and 10 are **pure figures** — no new content, they visualise what the
slide before already said. Say one sentence over each and move on. Slides 18–19
are **backup only**, shown solely if asked; they are not part of the timed talk.

| Part | Slides | Job | Target |
|---|---|---|---:|
| Opening | 1–3 | Frame the talk, state the two partial objectives up front | 2:00 |
| 1 — How it is built | 4–11 | Architecture, data, model, safety rebuild, grounding | 5:45 |
| 2 — What the measurements say | 12–15 | Results, retrieval, latency, trust | 3:40 |
| 3 — Limits and close | 16–17 | Own the limits, contributions | 1:45 |
| **Total** | 1–17 | | **~13:10** |

*Ghi chú: đừng giấu ba điểm yếu. Nói trước thì thành "biết tự đánh giá", để hội
đồng hỏi ra thì thành "giấu". Câu chốt của toàn bài: **mọi con số đều có script
sinh ra nó, và chỗ nào chưa đo thì ghi rõ là chưa đo.***

**If running long**, cut in this order: slide 14 (latency) to one sentence, then
trim slide 6's second bullet. **Never cut slides 8, 9 or 16** — the crisis
before/after table, the honest rebuild story, and the leakage number are the
three the panel is most likely to probe, and you want to have raised them
yourself.

---

## Slide 1 — Title

**On screen:** title, subtitle, defence line, institution, "screening aid, not
diagnostic" footer.

**Script (~25 s)**

> Good morning. My project is a screening application for academic stress in
> Vietnamese university students — two validated psychometric instruments, a
> fine-tuned Vietnamese encoder, and a retrieval-augmented advisory layer, all
> behind a deterministic safety rule.
>
> One framing sentence for the whole talk: **this is a screening and
> self-reflection aid, not a diagnostic tool**, and I will be explicit about
> which claims my measurements support and which they do not.

*Ghi chú: nói "not a diagnostic tool" ngay từ đầu — đề tài sức khoẻ tâm thần cần
hội đồng nghe bạn tự đặt giới hạn trước.*

---

## Slide 2 — The problem

**Script (~55 s)**

> Two kinds of tool exist today, and each is missing something. Validated
> questionnaires like DASS-21 give a trusted number and nothing else — no
> explanation, no next step. General chatbots give advice and explanation, but
> are anchored to no instrument, and will confidently invent advice with no
> source.
>
> This project keeps the validated instrument as the authority, and uses a
> language model only to explain and suggest, grounded in a curated knowledge
> base rather than its own parameters.
>
> One constraint shapes every decision that follows: in this domain, a wrong
> answer is not a bad user experience — it is potential harm. That is why the
> architecture is ordered the way the next slides show.

---

## Slide 3 — Objectives

**Script (~45 s)**

> Five objectives. O1, O4, O5 are met. O2 and O3 are **partly** met, and I am
> saying that here rather than letting it emerge later.
>
> O2: four systems produced comparable numbers on one frozen split — the fifth,
> the proposed pipeline, did not, for reasons on slide 12. O3: retrieval quality
> is measured and grounding is enforced, but the component ablation has not run
> — a provider quota limit, not a code problem.
>
> Everything else in this talk maps to one of these five rows.

*Ghi chú: slide này là "hợp đồng" với hội đồng — nói rõ 2 mục chỉ đạt một phần
ngay từ đầu để không ai bắt bẻ được là thổi phồng.*

---

## Slide 4 — Architecture

**Script (~35 s)**

> Here the ordering is a safety property, not convenience.
>
> The classifier and scoring run first — pure functions, nothing leaves the
> process. Then the crisis gate: **nothing is stored and no external service is
> called until it clears**, so a self-harm disclosure goes to helplines and is
> never saved.
>
> Persistence, retrieval and generation come last, because they can fail. If
> generation fails, the student still gets the deterministic results.

*Ghi chú: nói chậm nhất ở đây. "Cổng an toàn là thuộc tính, không phải tiện
tay" — câu đáng nhớ nhất của phần kiến trúc.*

## Slide 5 — [FIGURE] System architecture

**Script (~10 s)** — no new content, point at the diagram.

> The same ordering, as the code runs it: nothing right of the gate runs until
> it clears.

---

## Slide 6 — Data and the ground-truth label

**Script (~55 s)**

> 466 records, frozen split 326/70/70, seed 42.
>
> The ground truth is the **more severe** of the DASS-21 stress band and the
> PSS-10 category — chosen for screening asymmetry: a false alarm costs a
> student a helpline they didn't need, a miss costs support they did.
>
> Both source instruments are published and validated, deployed as the original
> English items. But the **composite itself** — combining two instruments into
> one four-class label — has not been separately validated as a scale. That is
> a stated limitation, not a solved one; §5.4 treats it as a construct-validity
> threat.
>
> The split is frozen everywhere because the classifier was fine-tuned on its
> training portion — redrawing it would leak into the test set.

---

## Slide 7 — The classifier

**Script (~50 s)**

> PhoBERT-base, fine-tuned, 4 epochs. Validation macro-F1 reaches 0.8403 at
> epoch two and plateaus completely — epochs three and four add nothing, so
> epoch two ships. Held-out test: accuracy 0.800, macro-F1 0.8013.
>
> Two honest notes. It is a three-class model, so in the unified four-class
> comparison its F1 on Severe is zero **by construction**, not failure. And it
> runs entirely offline — no network, no third party — which matters for
> private writing about mental health.

---

## Slide 8 — The safety rule: before and after

**Script (~55 s)**

> The crisis rule runs before the language model and before persistence — a
> disclosure never gets written to the database.
>
> Here is what changed, measured on a held-out set the rule had never seen.
> Precision 0.600 to 1.000. Recall **0.200 to 0.867**. Indirect ideation, zero
> of fourteen to eleven of fourteen. Zero false positives across twenty
> deliberately lethal-sounding idioms.
>
> The old number — recall 0.200 on unseen phrasing — is worse than what was
> previously published, 0.500. Part of that original figure came from the test
> set sharing wording with the lexicon.

*Ghi chú: đây là bảng quan trọng nhất. Đọc chậm hai số 0.200 → 0.867.*

---

## Slide 9 — Fixing it honestly was harder than fixing it

**Script (~70 s)**

> Twelve failures were already published in an earlier draft. Adding them
> straight into the phrase list and re-measuring on the same set would have
> been tuning against my own test set.
>
> So the order came first. I wrote a **new** sixty-item bilingual set and froze
> it — SHA-256 recorded — before touching the rule. I rebuilt the rule around
> six constructs from suicide-risk assessment — explicit intent, passive death
> wish, existence negation, perceived burdensomeness, preparation, escape —
> written from that taxonomy, not from my failures. Then I measured **once**.
>
> Re-measuring the held-out set afterwards, after fixing two regressions found
> on the development sets, gave **identical numbers** — the development work
> had no detectable effect on the number that matters.
>
> One limitation against my own result: I wrote both the patterns and the
> held-out set. Independent annotation would be stronger evidence. That is why
> the Vietnamese set's perfect 1.000/1.000 is a **development** number and
> deliberately not the headline.

*Ghi chú: khoảnh khắc mạnh nhất của bài. Bạn tự đưa bằng chứng chống lại chính
mình, kèm quy trình sửa. Đừng xin lỗi, chỉ trình bày.*

## Slide 10 — [FIGURE] How the safety rule was rebuilt

**Script (~15 s)**

> The order, made visible: freeze the held-out set, rebuild from the taxonomy,
> measure once, only then use the development sets — and confirm nothing
> changed afterwards.

---

## Slide 11 — What stops the model inventing advice

**Script (~60 s)**

> Three mechanisms. The prompt rule is absolute — the model may rephrase
> retrieved material, never add advice, techniques or phone numbers not present
> in it, even if it believes them true.
>
> Every suggestion cites the chunk it came from, by id. The service checks that
> citation against what was actually retrieved and **discards any the model
> invented** — a fabricated source cannot reach the student.
>
> And if retrieval returns nothing, **the generator is not called at all**. The
> system says advice is unavailable rather than filling the gap from its own
> knowledge. That is the difference between a grounded system and one that
> merely prefers to be grounded.

---

## Slide 12 — Main results

**Script (~75 s)**

> Two things to address directly.
>
> **The classical baseline wins.** TF-IDF with logistic regression reaches
> macro-F1 0.682, ahead of the fine-tuned transformer and the language model.
> That is not evidence transformers are worse — it is evidence about my data:
> 41 recurring templates, and n-grams are exceptionally good at recognising
> recurring surface forms. Slide 16 develops this.
>
> **The proposed system has no number, and I withdrew the one it used to
> have.** The harness was building its retrieval query differently from the
> deployed app — a measured 53% divergence in retrieved passages, now fixed and
> covered by a regression test. Then the re-run hit the provider's daily token
> cap at 38 of 70 items. At 46% unusable, my harness refuses to publish a score
> rather than describe the fallback label as if it were the system.
>
> I would rather stand here with an empty cell than a number I cannot defend.

*Ghi chú: câu cuối là câu chốt. Dừng một nhịp. Nếu bị hỏi "vậy hệ thống có tốt
không?" → "Chưa đo được, và em không đoán."*

---

## Slide 13 — The measurement that changed the system

**Script (~55 s)**

> Fifty-seven labelled queries, MRR 0.787, Recall@5 0.903 overall. But the
> finding that mattered was **how the query was built**.
>
> The original code discarded the student's sentence, searched on matched
> lexicon keywords instead, then appended a label like "student with High
> stress". On the sixteen queries that construction actually changes: keywords
> alone, 0.509 MRR. The sentence alone, 0.778 — already better. Sentence plus
> keywords, what ships now, 0.839. Appending the label hurt every variant
> tested — semantic noise pulling the embedding off-topic.
>
> Chosen by running all six candidate shapes through the harness, not
> intuition, and the harness reproduces the before/after on every run.

---

## Slide 14 — Latency

**Script (~35 s)**

> Measured over thirty runs per stage. The entire deterministic pipeline —
> scoring, safety rule, lexicon, retrieval, classifier — costs under 90
> milliseconds at the median. The safety gate itself: **0.05 milliseconds**,
> before any side effect. There is no performance argument against that
> ordering.
>
> Not measured: the generation call, tokens, cost per session — each is a
> billable request and the daily quota went to the comparison run.

---

## Slide 15 — Why these numbers can be trusted

**Script (~55 s)**

> 337 tests, 94% coverage on the application code — 70% once the offline
> evaluation scripts are counted too. Frozen split, seeded generation,
> disk-cached model responses: a repeated evaluation makes zero API calls.
>
> What matters more: no number exists without a script that produced it, and
> where nothing was measured the tooling writes an explicit "NOT RUN" marker.
>
> One example paying off twice. Failed model responses used to be discarded;
> now they're kept and classified — the next run showed 32 failures, **31
> rate-limit refusals and exactly one malformed JSON**, correcting an earlier
> claim of "seven invalid JSON" that was never evidence-based. And all five
> flagged literature references were checked against the publisher record —
> eight now carry a DOI, two were wrong and are corrected.

*Ghi chú: slide "chống đỡ" — quay lại đây nếu hội đồng nghi ngờ độ tin cậy số
liệu.*

---

## Slide 16 — The limitation that matters most

**Script (~65 s)**

> If you take one limitation from this talk, take this one.
>
> All text is generated from 41 Vietnamese sentence templates. The standard
> leakage control — exact duplicates across splits — passes perfectly, zero
> duplicates. That control is the **wrong instrument** here, and I can show
> why: the median nearest-neighbour similarity of a test item to its closest
> training item is **0.799**, and 34 of 70 test items exceed 0.80 — under three
> different similarity measures.
>
> The model is not being asked to detect stress. It is being asked to
> recognise templates it has already seen in a slightly different arrangement.
> Every text-classification figure here is a pipeline demonstration, not
> evidence of stress-detection ability — and it's the honest explanation for
> why TF-IDF won on slide 12.

*Ghi chú: nếu chỉ kịp nói 1 limitation, nói cái này. Vừa là điểm yếu lớn nhất,
vừa là đóng góp — chứng minh exact-duplicate check là công cụ sai ở đây.*

---

## Slide 17 — Conclusion

**Script (~40 s)**

> A working, layered screening system where the deterministic components run
> first and can pre-empt the generative ones. A crisis-detection set in both
> languages, measured without tuning against it, every error published
> verbatim. A demonstration that exact-duplicate checking is inadequate for
> template-generated data, with the measurement to prove it. A harness where a
> missing measurement looks missing.
>
> What it does not yet have is real data — the difference between
> demonstrating a pipeline and demonstrating stress detection. That is where
> the thesis goes next.
>
> Thank you. I'm happy to take questions.

---

## Slides 18–19 — Backup (Q&A only, not part of the timed talk)

**18 — Where the headline label comes from.** Pull up only if asked "the model
could contradict the questionnaire — which one does the student see?" The
validated instrument owns the headline; the model explains; disagreement is
shown, not hidden.

**19 — Evidence provenance.** Pull up only if the panel questions
reproducibility. Every number traces: committed source → script → artefact.

---

# Q&A preparation

*Ghi chú: chỉ để ôn, không lên slide. Trả lời bằng sự thật trước, không bào
chữa.*

**Q: "Your title says LLM-powered. Which table evaluates the LLM?"**
> The zero-shot row on slide 12, and retrieval evaluation on slide 13. The
> proposed-pipeline row is empty — a retrieval-path bug I found and fixed,
> then a provider quota limit. The ablation is written and partially cached;
> it's a quota problem, not a code problem.

**Q: "Recall went from 0.500 to 0.867 — is 0.867 the real number?"**
> It's the held-out number, measured on a set frozen before the rule existed —
> that procedure is what makes it meaningful. The caveat I volunteer myself:
> I wrote both the patterns and the held-out set. Independent annotation is
> the natural next step to strengthen it further.

**Q: "Why is TF-IDF beating your transformer?"**
> My data, not my architecture. 41 templates, median near-duplicate similarity
> 0.799. N-grams excel at recognising recurring surface forms — evidence for
> the dataset limitation on slide 16, not a modelling conclusion.

**Q: "The LLM could contradict the questionnaire. Which one does the student see?"**
> The questionnaire. The headline level comes from the validated instrument
> whenever one exists; the model explains and suggests. Where they differ, the
> student is told explicitly — see backup slide 18.

**Q: "Your 4-class label is not a validated scale."**
> Correct, stated on slide 6. A conservative composite of two validated
> instruments, with no independent psychometric validation of the composite
> itself. Validating it is outside this scope.

**Q: "How do I know your numbers are reproducible?"**
> Frozen split, seeded generator, disk-cached model responses, exact evaluated
> dataframe written on every run — see backup slide 19. Two known gaps: one
> intermediate CSV's build script is missing from the repo, and dependency
> versions are unpinned. Both are in the report's appendix.

**Q: "What stops the model inventing a helpline number?"**
> Three things on slide 11: absolute grounding in the prompt, citation ids
> verified against what was retrieved, and empty retrieval means the generator
> is never called. Not yet measured: faithfulness — whether the cited passage
> genuinely supports the sentence citing it.

**Q: "PhoBERT is Vietnamese — does it even run on the English interface?"**
> Only on Vietnamese input; the language gate skips it on English and falls
> back to the bilingual lexicon. Every PhoBERT number in this talk was measured
> on the Vietnamese-only evaluation corpus, not on what an English-writing
> student's session exercises. Stated as a limitation in the report, §5.3.

---

# Optional extra visuals (not required — the deck already has its figures)

Slides 5, 10, 18, 19 already carry the mermaid diagrams that matter. These four
matplotlib PNGs exist on disk and are **not currently pasted anywhere**; add
one only if you want a data-distribution or training-curve visual alongside its
slide's table.

| File | Regenerate with | Would sit on |
|---|---|---|
| `data/eval/fig_4_2_label_distribution.png` | `python -m app.eval.make_figures` | slide 6 |
| `data/eval/fig_4_3_training_curves.png` | same | slide 7 |
| `data/eval/fig_4_6_macro_f1.png` | same | slide 12 |
| `data/eval/fig_4_9_latency.png` | `python -m app.eval.latency_eval --repeats 30` | slide 14 |

---

# BUỔI THUYẾT TRÌNH — NHỮNG GÌ CẦN BIẾT (tiếng Việt)

## 1. Tóm tắt đề tài trong 3 câu, học thuộc

> Em xây một ứng dụng sàng lọc căng thẳng học tập, dùng DASS-21 và PSS-10 làm
> thẩm quyền chính, LLM chỉ để giải thích và gợi ý có căn cứ trích dẫn. Toàn bộ
> hệ thống đứng sau một luật an toàn xác định (deterministic) chạy trước mọi
> thứ khác — không văn bản khủng hoảng nào từng được lưu lại. Đây là công cụ
> sàng lọc, không phải công cụ chẩn đoán.

## 2. Cấu trúc 17 slide nói + 2 slide dự phòng

Slide 5 và 10 **không có nội dung mới** — chỉ là hình minh hoạ cho slide 4 và
9, nói 1 câu rồi qua. Slide 18–19 **chỉ mở khi bị hỏi**, không nằm trong phần
trình bày có tính giờ.

```
1  Tiêu đề                    10 [HÌNH] quy trình sửa an toàn
2  Vấn đề                     11 Chống bịa lời khuyên (RAG)
3  5 mục tiêu                 12 Kết quả chính
4  Kiến trúc                  13 Phép đo đổi cả hệ thống (RAG query)
5  [HÌNH] kiến trúc           14 Latency
6  Dữ liệu + nhãn             15 Vì sao số liệu đáng tin
7  PhoBERT                    16 Hạn chế lớn nhất (leakage)
8  An toàn: trước/sau (bảng)  17 Kết luận
9  Sửa an toàn — quy trình    18-19 [DỰ PHÒNG, chỉ khi bị hỏi]
```

## 3. Ba khoảnh khắc phải nhớ chính xác từng số

Đây là ba slide **không được cắt** dù thiếu giờ — chúng là ba điều hội đồng gần
như chắc chắn hỏi, và bạn đã có sẵn câu trả lời tốt hơn họ tưởng:

| Slide | Con số phải thuộc | Ý nghĩa |
|---|---|---|
| **8** | Recall **0.200 → 0.867** | Rule an toàn cũ tệ hơn cả số đã công bố (0.500); rule mới đo trên tập chưa từng thấy |
| **9** | Đo **một lần**, sau khi đóng băng tập test **trước khi** sửa rule | Đây là *cách* làm cho con số đáng tin — không phải bản thân con số |
| **16** | Median similarity **0.799**, **34/70** mẫu test > 0.80 | Vì sao TF-IDF thắng — không phải vì transformer kém, mà vì dữ liệu là template |

## 4. Bảng số liệu cốt lõi — mang theo, đừng chỉ nhớ

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| PhoBERT val macro-F1 / test acc | 0.8403 / 0.800 | `phobert_run.log` |
| TF-IDF + LogReg | acc 0.6857, F1 0.6816 | `data/eval/comparison.csv` |
| Crisis rule (held-out, sau sửa) | P 1.000 · R 0.867 · F1 0.929 | `data/eval/crisis_eval_heldout.md` |
| Retrieval MRR / Recall@5 | 0.787 / 0.903 | `data/eval/retrieval_eval.md` |
| Latency cổng an toàn | 0.05 ms | `data/eval/latency.md` |
| Test suite | 337 pass, 94% (70% cả eval) | chạy `pytest --cov=app` |
| Leakage (headline difflib) | median 0.799, 34/70 | `data/eval/leakage.md` |

## 5. Ba điều tuyệt đối không được nói sai

- ❌ **"Crisis rule chạy đầu tiên trong pipeline"** — SAI. Thứ tự thật: classifier + scoring (hàm thuần) chạy trước, rồi mới tới cổng crisis, vì cổng cần điểm DASS depression severity từ bước scoring. Nói đúng: *"mọi thứ trước cổng là hàm thuần, không ghi/gửi/hiện gì — cổng là ranh giới tác dụng phụ, không phải bước đầu tiên."*
- ❌ **"Model dùng là GPT-4o-mini / của OpenAI"** — SAI. Model thật là `openai/gpt-oss-120b` chạy qua **Groq**. Nếu bị hỏi tên nhà cung cấp, nói đúng "Groq" — đừng nói "OpenAI" theo phản xạ cũ.
- ❌ **"Coverage 83%"** — con số cũ, đã lỗi thời. Con số đúng hiện tại: **94%** trên code sản phẩm, **70%** nếu tính cả script eval offline.

## 6. Nếu bị hỏi vặn về quyết định thiết kế

- **"Nhãn 4 lớp này có phải thang đo đã kiểm định không?"** → Không, và slide 6 đã tự nói vậy. Đây là *composite operational measure* — lấy mức nặng hơn giữa DASS-21 và PSS-10 — bản thân hai thang gốc đã kiểm định, nhưng phép gộp thì chưa. Đừng gọi nó là "em tự nghĩ ra" (nghe như lỗi); gọi đúng là "quyết định thiết kế có nêu rõ giới hạn".
- **"PhoBERT có chạy trên input tiếng Anh không?"** → Không. Cổng ngôn ngữ chặn nó lại trên input tiếng Anh, rơi về lexicon song ngữ. Mọi số liệu PhoBERT trong bài đo trên corpus tiếng Việt, không phải trên phiên làm việc thực tế của một sinh viên viết tiếng Anh — đây là giới hạn đã ghi trong §5.3.
- **"Sao không chạy được ablation?"** → Bị chặn bởi hạn mức token/ngày của provider, không phải lỗi code. Harness đã viết xong, có test, và 38/70 mục đã có cache sẵn.

## 7. Checklist trước khi vào phòng

- [ ] Mở đúng file `PreThesis_Slides_v6_with_figures.pptx` (không phải bản `_v2`/`_v3`/`_v4` cũ)
- [ ] Chạy `python scripts/warm.py` nếu định demo app trực tiếp — tránh 25 giây màn hình trắng
- [ ] Tắt auto-translate trình duyệt nếu demo Streamlit
- [ ] Không bấm toàn "2" ở DASS-21 câu 17 và 21 trừ khi cố ý demo màn hình khủng hoảng
- [ ] Mang theo bảng số liệu ở mục 4 (in giấy hoặc điện thoại) — không dựa hoàn toàn vào trí nhớ khi bị hỏi dồn

## 8. Nếu thời gian gấp

Cắt theo đúng thứ tự: slide 14 (latency) xuống 1 câu → rút bullet thứ hai của
slide 6. **Không bao giờ cắt slide 8, 9, hoặc 16** — đó là ba nơi hội đồng
nhiều khả năng hỏi nhất, và bạn muốn là người tự nêu ra trước.
