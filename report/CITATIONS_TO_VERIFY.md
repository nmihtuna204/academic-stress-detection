# Citations Requiring Verification

Every reference in `PreThesis_Report.md` marked `[VERIFY]` is listed here. **Do not submit the report until each row is either confirmed against the actual publication or removed.** A fabricated or misattributed citation is treated more severely by a committee than a missing one.

Rows without `[VERIFY]` in the report ([1], [2], [3], [5], [9], [10], [11], [13], [14], [15], [16], [17], [18], [19], [20]) are standard, widely reproduced references whose details the author should still confirm once against the publisher record — but they are not flagged as uncertain.

---

## Flagged references — ALL VERIFIED 2026-09-10

Every row below was checked against the publisher record or the ACL Anthology
canonical BibTeX. Two corrections were required; three were already exact.

| Ref | Verdict | What changed |
|---|---|---|
| **[4]** Tran, Tran, Fisher — BMC Psychiatry 2013 | ⚠️ **Corrected** | Third author is **J. R. W. Fisher** (Jane Rosamond Woodward Fisher), not "J. Fisher". Title, vol. 13, art. 24, 2013 all confirmed. DOI 10.1186/1471-244X-13-24 added. Verified via the Monash institutional record (the authors' own institution). |
| **[6]** Coppersmith et al. — CLPsych 2015 | ✅ **Exact** | Author list, order, pages 31–39 and year all correct. Full proceedings title and DOI 10.3115/v1/W15-1204 added. |
| **[7]** Turcan & McKeown — Dreaddit 2019 | ✅ **Exact** | Authors, pages 97–107, year correct. Workshop name expanded to the official "10th Int. Workshop on Health Text Mining and Information Analysis (LOUHI 2019)"; DOI 10.18653/v1/D19-6213 added. |
| **[8]** Losada & Crestani — CLEF 2016 | ⚠️ **Completed** | The "CLEF vs. LNCS" question raised here resolves as *both*: it is the CLEF 2016 conference, published in Springer **LNCS vol. 9822**, pp. 28–39. Full proceedings title, volume, publisher and DOI 10.1007/978-3-319-44564-9_3 added. |
| **[12]** Nguyen et al. — ViSoBERT, EMNLP 2023 | ⚠️ **Corrected** | Author initials did **not** match the record. Was "Q.-N. Nguyen, T. C. Phan, D.-V. Nguyen, K. Van Nguyen"; the ACL Anthology canonical BibTeX gives **Nguyen, Nam; Phan, Thang; Nguyen, Duc-Vu; Nguyen, Kiet**. Confirmed **EMNLP main conference** (not Findings), pp. 5191–5207, DOI 10.18653/v1/2023.emnlp-main.315. |

**Sources used for verification**

- [4] <https://research.monash.edu/en/publications/validation-of-the-depression-anxiety-stress-scales-dass-21-as-a-s/> · DOI 10.1186/1471-244X-13-24
- [6] <https://aclanthology.org/W15-1204/> (canonical BibTeX)
- [7] <https://aclanthology.org/D19-6213/> (canonical BibTeX)
- [8] <https://tec.citius.usc.es/ir/code/dc.html> (authors' own citation request) · <https://link.springer.com/chapter/10.1007/978-3-319-44564-9_3>
- [12] <https://aclanthology.org/2023.emnlp-main.315/> (canonical BibTeX)

**One residual caveat on [12].** The ACL Anthology renders the first author as
"Nam Nguyen"; some secondary indexes render "Quoc-Nam Nguyen". The Anthology
BibTeX is the citable form for an ACL paper and is what the report now uses. If
the submitted version is checked against the PDF's own author line and differs,
prefer the PDF.

**On [4] and the deployed instrument.** This reference is no longer load-bearing
for the deployed DASS-21 wording. The application now uses the original English
Lovibond & Lovibond items verbatim, so the Vietnamese translation-fidelity
question does not arise in the deployed path; [4] supports only the
related-work claim that a validated Vietnamese DASS-21 exists.

## Unsourced claims (no citation number assigned)

| Location | Claim | Status |
|---|---|---|
| §1.1 | "Epidemiological studies of stress, anxiety, and depression prevalence among Vietnamese university populations have been conducted, and several report prevalence figures substantially above general-population baselines" | **No source verified.** The report deliberately quotes **no prevalence figure anywhere**. If a Vietnamese epidemiological study is located and verified, add it as a numbered reference and the sentence may quote its figure. If none is located, the sentence stands as written — it makes no numeric claim. **Do not invent a percentage.** |
| §2.1 | Vietnamese validation status of the PSS-10 | Stated in the report as unclear within the scope of the review. If a Vietnamese PSS-10 validation study is located, add it and update §2.1 and §5.3. |
| §5.3, Appendix A.2 | Source of the deployed Vietnamese PSS-10 item wording | **Unknown.** The implementation carries no citation. Either locate the source translation or state in the final report that the wording is the author's own, which changes it from a validated instrument to an unvalidated translation and must be reflected in the limitations. |

---

## Suggested additions if the literature review is expanded

These are not currently cited and are offered as leads only — **verify before adding**:

- A Vietnamese-language mental-health corpus or shared task, if one has been published since this review.
- A survey of LLM safety in mental-health applications, to strengthen §2.4, which currently leans on a general hallucination survey [16].
- Published guidance on digital mental-health screening tools (e.g. from a health authority or professional body) to support the responsible-deployment argument in §5.5.

---

## Verification checklist

- [x] All five `[VERIFY]` references confirmed against publisher records, or removed
- [ ] Vietnamese DASS-21 published item list obtained and compared item-by-item with Appendix A.1
- [ ] Vietnamese PSS-10 wording sourced, or Appendix A.2 relabelled as an unvalidated translation
- [ ] Every reference [1]–[20] cited at least once in the body
- [x] No `[VERIFY]` marker remains anywhere in `PreThesis_Report.md`
- [ ] Reference numbering still matches order of first appearance after any additions or removals
