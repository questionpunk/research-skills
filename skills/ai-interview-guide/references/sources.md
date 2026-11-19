# AI interview guide: method sources

Checked on 2026-11-12, with additions on 2026-11-19 (marked). "Verified" means the claim was read in the
primary source or its abstract on that date.

## Contents

- What the evidence on AI-moderated interviews says
- Vendor documentation
- Interview method
- Conventions this skill sets
- Where practitioners disagree
- Pitfalls

## What the evidence on AI-moderated interviews says

### Geiecke and Jaravel, "Conversations at Scale: Robust AI-led Interviews with a Simple Open-Source Platform"

Working paper, first circulated 2024 (CEPR DP 19705), version read: 16 July 2025.
<https://conference.nber.org/conf_papers/f221279.pdf> (abstract: <https://ideas.repec.org/p/cpr/ceprdp/19705.html>).
Published as "Conversations at Scale: Robust AI-Led Interviews", *Review of Economic Studies*, online 27
October 2026, <https://doi.org/10.1093/restud/rdag114> (title, journal and date confirmed on Crossref on
2026-11-19; the journal text was not read). The figures below are from the 16 July 2025 working-paper
version and may differ in the article. Verified in the full text:

- **The moderator prompt (as printed in the paper).** One LLM agent, one prompt, made of an interview
  outline plus six general instructions drawn from Small and Calarco, *Qualitative Literacy* (2022): (1) guide the interview in a
  non-directive, non-leading way and ask follow-up questions; never suggest possible answers, "not even a
  broad theme"; if a respondent cannot answer, ask again from a different angle before moving on;
  (2) collect "palpable evidence": specific events, situations, people, examples, not generalizations;
  (3) "cognitive empathy": ask why the respondent holds a view and where it comes from; (4) do not assume
  a view or provoke defensiveness; (5) "Ask only one question per message"; (6) stay on the interview's
  purpose and redirect off-topic conversation. Example follow-ups in the prompt: "Can you tell me more about
  the last time you did that?", "What has that been like for you?", "Why is this important to you?", "Can
  you offer an example?". The outline also fixes the first question word for word, so every interview
  starts the same way.
- **Quality against experts (text chat).** Sociology PhD students graded 20 transcripts twice (40 grades)
  on a 1 to 5 scale where 3 is an average human expert using the same online text chat. Mean 2.95. No
  transcript got a 5: "the AI-led interviews never match the best human experts". Agreement between the
  two graders of a transcript was modest (correlation 0.41).
- **Four modalities (June and July 2025).** Graded against a top expert in a 30-minute online text chat:
  AI voice 3.9, human face to face 3.6, AI text 3.2, human text chat 2.8. Graded against a top expert face
  to face: human face to face 3.6, AI voice 3.4, AI text 2.8, human text chat 2.3. The authors' summary:
  high quality, "approaching the performance of human experts", voice more so than text.
- **Against one open text box.** Respondents in the AI interview wrote 142% more words (460 against 190).
- **Respondent preference.** 43% would rather repeat the interview with an AI, 19% with a human, 38% did
  not mind. 76% would not have preferred a text box. Complaints quoted: "the AI was too fast. It felt like
  an interrogation", questions "seemed repetitive".
- **Limits the authors state.** Models "struggle to always restrict their message to contain only a single
  question". Panel respondents expect to spend less than thirty minutes, so these interviews are much
  shorter than academic human interviews. Some respondents answer with an LLM or rush. Proprietary models
  mean the provider processes the data, which needs a matching consent form. Their outlines cap the session
  at "up to around 30 questions" or "up to 30 minutes".

**The open-source repository** differs from the paper. <https://github.com/friedrichgeiecke/interviews>,
file `config.py`, read on 2026-11-12 from a copy downloaded that day (code under the PolyForm Noncommercial
licence, documentation under CC BY-NC 4.0, so nothing is copied here). Its general instructions have nine
points, not six. Beyond the paper's principles, the configuration tells the model, in substance: to keep
its instructions from the respondent; to ask one question at a time without numbering; to keep moving
forward and not return to finished topics; to avoid long paraphrases and effusive affirmations; to prefer
direct invitations to elaborate over tentative ones; not to answer questions about itself; to ask before
closing whether anything is left to discuss; and to answer with a fixed code, and nothing else, for
problematic content and for the end of the interview, which the front end turns into a closing message.
The custom-LLM prompt in `brief-template.md` covers the same ground in its own words and adds two things
the repository does not have: an answer to "are you a human?" and a rule for attempts to instruct the model.

### Chopra and Haaland, "Conducting Qualitative Interviews with AI"

CESifo Working Paper 10666, first version 2023, revised since.
<https://www.ifo.de/en/cesifo/publications/2023/working-paper/conducting-qualitative-interviews-ai>
(2023 version: <https://ideas.repec.org/p/kud/kucebi/2306.html>). Verified from the two abstracts only:

- 2023 version: 395 AI-assisted interviews on why people do not hold stocks; high interviewee
  satisfaction; "a majority" strictly preferred the AI-assisted interview to a human-led one (no percentage
  in the abstract).
- Current version: AI-led interviews give thematically richer answers than other ways of collecting
  qualitative data in surveys; the gain comes mainly from dynamic probing questions; the answers predict
  behaviour six months later; thematic saturation is reached in small samples similar to human-led studies.
- The versions differ (the first CESifo abstract reported 381 interviews and an eight-month follow-up).
  Cite the version you read.

### Wuttke, Aßenmacher, Klamm, Lang, Würschinger and Kreuter, "AI Conversational Interviewing"

arXiv:2410.01824 (2024); LaTeCH-CLfL 2025. <https://arxiv.org/abs/2410.01824>. Verified in the full text
(v1):

- Very small study: 5 AI-led and 6 human-led interviews with university students on political topics,
  GPT-4 Turbo, respondents could type or speak. AI interviews averaged 22 minutes, human ones 16.
- Answers were longer with the AI (52.39 against 32.81 words on average), and spoken answers were longer
  than typed ones (63 against 21 tokens).
- Both kinds of interviewer broke the interviewing guidelines. The AI accounted for 88% of the violations
  of the follow-up rule (it often did not ask a follow-up it should have), although the authors' pre-tests
  had not shown this. The AI accounted for 67% of "judging" violations, for example praising an answer
  ("Your definition of politics is quite insightful"). Human interviewers accounted for 94% of
  active-listening violations and 75% of the cases of steering the respondent towards an answer.
- Participants were equally satisfied overall (3.8 in both arms) but rated the AI interview less
  interesting and were less willing to repeat it; audio failures, transcription errors and replies slower
  than five seconds were reported.
- Recommendations: write the interviewer behaviour down for the specific study (how often to follow up,
  how deep, how formal), pre-test the prompt thoroughly because small prompt changes have large side
  effects, and choose the input mode deliberately because typed and spoken answers differ.

### What this adds up to

Three papers, two from economics (one now a journal article, figures above from its working-paper
version), one tiny. They agree that an AI moderator with a short,
principled prompt produces usable transcripts and longer answers than a text box, and that follow-up
probing is where the value comes from. They also agree on the weak spots: more than one question per
turn, missed or repetitive follow-ups, evaluative praise, and no match for the best human interviewers.
None of them studied commercial customer research, churn or pricing topics.

## Vendor documentation (how hosted tools are configured; not evidence)

Read at the URLs on 2026-11-12. These pages describe products and give the vendors' advice. They show what
settings exist; they do not show that a setting improves an interview.

- **Marvin**, "Best practices to use the AI interviewer",
  <https://help.heymarvin.com/en/articles/13539018-best-practices-to-use-the-ai-interviewer>: probing depth
  is set per question at three levels (the middle one is described as at least two follow-ups, the top one
  as three to seven); research goals are a separate field the participant does not see; instructions sit
  with the relevant section of the guide; voice can be a real-time conversation or turn-based recording,
  the latter suggested for participants without a quiet place; consent collected through a conditional
  question can leave incomplete sessions when someone declines; run a test interview before launch.
- **Listen Labs**, "Common AI-moderated research questions",
  <https://listenlabs.ai/blog/common-ai-moderated-research-questions>: probing can be set per question
  (never, on a short answer, or always, with one to two follow-ups), with a cap and a stated focus.
- **Maze**, "AI moderator discussion instructions",
  <https://help.maze.co/articles/4725806286-ai-moderator-discussion-instructions>: instructions attach to a
  whole goal or to a single question, and do not carry over; useful context includes recruitment criteria,
  usage patterns, boundaries and conditional follow-ups; the moderator already asks one question at a time,
  stays neutral and asks for a recent example; two concrete instructions are preferred to a long general
  list; address the moderator, not the participant; pilot.
- **Outset**, "Improving participant experience in AI-moderated interviews",
  <https://help.outset.ai/articles/6901060570-improving-participant-experience-in-ai-moderated-interviews>:
  the AI follows the guide as written, so overlapping questions are asked twice; take the full interview
  yourself before launch; after launch watch drop-off, answers getting shorter late in the session, the
  same answer across questions and signs of confusion; a "context for AI" field holds terminology and
  participant phrasing.

Vendor conventions that this skill does **not** rely on as evidence: Marvin's follow-up counts per level,
Outset's "about 20 to 30 minutes" (the skill's 20-minute default and 30-minute ceiling rest on Geiecke and
Jaravel and Wuttke et al. instead) and its 70/30 mix of qualitative and quantitative questions. None comes
with data.

## Interview method

- **Past behaviour, not opinions or futures.** Fitzpatrick, *The Mom Test* (2013),
  <https://www.momtestbook.com>: talk about the person's life, not your idea; ask about specifics in the
  past, not generics or opinions about the future; talk less. Torres, story-based interviewing,
  <https://www.producttalk.org/glossary-discovery-story-based-interviewing/> (verified on the page): collect
  "specific accounts of past behavior"; ask "Tell me about the last time you watched Netflix" instead of
  "How often do you watch Netflix?"; when the participant drifts into generalities, guide them back to the
  specific story.
- **Guide structure.** Rosala, "Writing an Effective Guide for a UX Interview", Nielsen Norman Group, 2021,
  <https://www.nngroup.com/articles/interview-guide/> (verified): write research questions first, turn
  closed questions into broad open ones, order them logically with easy warm-up questions first, prepare
  follow-up and probing questions for each main question, pilot with at least one participant and revise.
  Portigal, *Interviewing Users*, 2nd ed., Rosenfeld Media 2023,
  <https://rosenfeldmedia.com/books/interviewing-users-second-edition/>: field guide as a flexible plan,
  silence, and asking for stories.
- **Question types.** Spradley, *The Ethnographic Interview* (1979): descriptive questions first (grand
  tour, then mini tour), then structural questions (how the person organises things), then contrast
  questions (how two things differ). Kvale, *InterViews* (1996; later editions with Brinkmann): nine types,
  introducing, follow-up, probing, specifying, direct, indirect, structuring, silence and interpreting;
  direct questions are held back until the participant has given their own account.
- **Laddering.** Reynolds and Gutman, "Laddering theory, method, analysis, and interpretation", *Journal
  of Advertising Research* 28(1), 1988, 11–31: a one-to-one interview using a series of directed probes to
  link attributes to consequences to personal values.
- **How many interviews.** Hennink and Kaiser, "Sample sizes for saturation in qualitative research: A
  systematic review of empirical tests", *Social Science & Medicine* 292, 2022, 114523,
  <https://pubmed.ncbi.nlm.nih.gov/34785096/> (abstract verified): the empirical studies reached saturation
  in 9 to 17 interviews, mostly code saturation in homogeneous populations with narrow aims; meaning
  saturation and mixed populations needed more. Guest, Bunce and Johnson, "How Many Interviews Are
  Enough?", *Field Methods* 18(1), 2006, 59–82, <https://doi.org/10.1177/1525822X05279903> (abstract
  verified): in 60 interviews, saturation occurred within the first 12 and the basic elements of metathemes
  appeared as early as 6. Hennink, Kaiser and Marconi, "Code Saturation Versus Meaning Saturation: How Many
  Interviews Are Enough?", *Qualitative Health Research* 27(4), 2017, 591–608,
  <https://doi.org/10.1177/1049732316665344> (added 2026-11-19; known from the abstract): code saturation
  at 9 interviews, meaning saturation, a full understanding of the issues, at 16 to 24. The field review
  asks whether later interviews still add codes or depth, not only new codes.

## Conventions this skill sets (not findings)

These numbers are working defaults chosen for the skill. No source above tested them; the pilot is what
checks them.

- **Pilot of 3 to 5 interviews.** NN/g asks for at least one pilot participant. The skill asks for 3 to 5
  because an AI moderator's behaviour varies between sessions and because Wuttke et al. saw follow-up
  failures in the field that their pre-tests had missed.
- **Default time budget of 20 minutes**, and never above 30 minutes for panel respondents. The ceiling is
  from Geiecke and Jaravel (panel respondents expect less than thirty minutes; their sessions were capped at
  30 minutes). 20 is a convention inside that range; Wuttke et al.'s AI interviews averaged 22 minutes.
- **Probe depth per question: none = 0 follow-ups, light = up to 1, deep = up to 3.** A convention. Setting
  depth per question follows how hosted tools are configured (vendor documentation above). The limits
  answer two observed failures: follow-ups that never come (Wuttke et al.) and interviews that feel
  repetitive or like an interrogation (Geiecke and Jaravel). Vendors count their levels differently.
- **Planning ratio of about one interviewer turn per minute.** Derived from Geiecke and Jaravel's outlines
  ("up to around 30 questions" in sessions of up to 30 minutes). It is a ceiling used in a prompt, not a
  measured pace, and it comes from typed interviews. A question costs one turn plus its follow-ups (none 1,
  light 2, deep 4), so 20 minutes fits, for example, a warm-up, three deep and three light questions and
  the last question (1 + 12 + 6 + 1 = 20).
- **"Try to cut two more questions."** A practitioner heuristic for trimming a finished guide. No source
  for it could be verified; the number is arbitrary and the point is to make a second cutting pass.
- **First field check after 10 completed interviews.** A convention; scale it to the sample.
- **Five test personas** (terse, rambling, off-topic and instructing, distressed, declines one question). A
  convention of this skill for the self-run; they cover the failure modes listed under "Pitfalls" and the
  consent screen's promise that a question can be skipped.
- **Ending by turn count and a time line from the application.** The model asks the last question by the
  last turn of the budget; the application supplies the time left, because a model cannot measure time.
  A convention. The Geiecke and Jaravel repository goes further: the model returns only an end code and
  the front end shows the closing (described above).
- **Explicit agreement to recording for voice or video.** Some jurisdictions require every party's
  consent to a recording. Stated as a precaution, not legal advice.
- **Segments of about 12 participants.** A planning figure taken from the saturation studies above (12 in
  Guest et al., inside Hennink and Kaiser's 9 to 17). It applies to one homogeneous segment.

## Where practitioners disagree

- **Hypothetical and concept questions.** The Mom Test and Torres treat "would you" answers as worthless
  for predicting behaviour. Concept and reaction questions remain standard in concept testing. The skill
  keeps them out of the must-ask list unless the study is a concept reaction, and never counts them as
  evidence of demand.
- **"Why" questions.** Geiecke and Jaravel's prompt offers "Why is this important to you?" as a follow-up,
  and laddering is built on why-probes. A common practitioner caution, not traced to a source here, is that
  "why" about a person's action reads as a demand to justify. The skill uses "what" and "how" forms and allows a plain "why" only about a view
  or preference the participant has just stated.
- **Where consent is collected.** Geiecke and Jaravel start the interview with a fixed first message;
  Marvin's documentation advises screening or consent before the session. The skill puts disclosure and
  consent on a screen before the session and keeps the opener short.
- **How much to instruct the moderator.** Maze's documentation prefers a few concrete instructions, and
  Geiecke and Jaravel report that in part of their evaluation the
  experts graded a version with minimal general instructions higher, because it felt less prescriptive.
  Long rule lists are not automatically better.
- **Saturation as a stopping rule.** The 9 to 17 range comes from homogeneous groups and code saturation.
  It is not a target for a mixed customer base, and some qualitative researchers reject saturation as a
  criterion altogether.
- **AI against human moderators.** Chopra and Haaland and Geiecke and Jaravel report favourable results;
  Wuttke et al. report comparable data with different errors. All are working papers or small studies, and
  expert graders disagreed with each other.

## Pitfalls

- Several questions in one turn (the failure Geiecke and Jaravel say models still show).
- A follow-up that should have been asked and was not, or the same follow-up asked again and again.
- Praise or evaluation of an answer ("great point"), which Wuttke et al. coded as a neutrality violation.
- The moderator summarising the answer in its own words and asking the participant to agree.
- Suggesting possible answers or themes inside a question.
- "Would you use or pay for X?" treated as the key evidence.
- No statement that the interviewer is an AI, or that a model provider processes the answers.
- No record of which must-ask questions each interview covered.
- Sensitive disclosures (health, money trouble, distress) with no instruction for the moderator.
- A consent screen that promises a skip the moderator prompt does not honour.
- The last question asked twice, or the closing sent in the same message as the last question.
- Grading coverage from transcripts a tool returned cut short.
