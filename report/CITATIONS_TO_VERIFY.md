# Citations Requiring Verification

Every reference in `PreThesis_Report.md` marked `[VERIFY]` is listed here. **Do not submit the report until each row is either confirmed against the actual publication or removed.** A fabricated or misattributed citation is treated more severely by a committee than a missing one.

Rows without `[VERIFY]` in the report ([1], [2], [3], [5], [9], [10], [11], [13], [14], [15], [16], [17], [18], [19], [20]) are standard, widely reproduced references whose details the author should still confirm once against the publisher record — but they are not flagged as uncertain.

---

## Flagged references

| Ref | Claim as written | What to verify | Where to check |
|---|---|---|---|
| **[4]** | T. D. Tran, T. Tran, J. Fisher, "Validation of the depression anxiety stress scales (DASS) 21 as a screening instrument for depression and anxiety in a rural community-based cohort of northern Vietnamese women," *BMC Psychiatry*, vol. 13, art. 24, 2013 | Author initials and order · exact title · volume and article number · year. **Critically:** confirm this is the source the deployed Vietnamese DASS-21 wording derives from, and obtain the published Vietnamese item list for the Appendix A comparison (§5.3). | BMC Psychiatry (open access); DOI lookup |
| **[6]** | G. Coppersmith, M. Dredze, C. Harman, K. Hollingshead, M. Mitchell, "CLPsych 2015 shared task: Depression and PTSD on Twitter," *Proc. 2nd Workshop on CLPsych*, 2015, pp. 31–39 | Full author list and order · exact page range · whether the shared-task overview paper is the correct citation for the general claim made in §2.2 | ACL Anthology |
| **[7]** | E. Turcan, K. McKeown, "Dreaddit: A Reddit dataset for stress analysis in social media," *Proc. LOUHI @ EMNLP*, 2019, pp. 97–107 | Exact workshop name and page range · year | ACL Anthology |
| **[8]** | D. E. Losada, F. Crestani, "A test collection for research on depression and language use," *CLEF*, 2016, pp. 28–39 | Exact proceedings title (CLEF vs. LNCS volume) · page range · whether this is the correct foundational eRisk citation | CLEF proceedings / Springer LNCS |
| **[12]** | Q.-N. Nguyen, T. C. Phan, D.-V. Nguyen, K. Van Nguyen, "ViSoBERT: A pre-trained language model for Vietnamese social media text processing," *Proc. EMNLP*, 2023 | Full author list and order · whether main conference or Findings · page range | ACL Anthology |

---

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

- [ ] All five `[VERIFY]` references confirmed against publisher records, or removed
- [ ] Vietnamese DASS-21 published item list obtained and compared item-by-item with Appendix A.1
- [ ] Vietnamese PSS-10 wording sourced, or Appendix A.2 relabelled as an unvalidated translation
- [ ] Every reference [1]–[20] cited at least once in the body
- [ ] No `[VERIFY]` marker remains anywhere in `PreThesis_Report.md`
- [ ] Reference numbering still matches order of first appearance after any additions or removals
