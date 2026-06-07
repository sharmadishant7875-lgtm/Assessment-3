# Senior Azure Data Engineer — Take-Home Assessment

**Read this file in full before you open anything else in the repo.**

This file explains what we expect from you, how to submit, and the rules of engagement. The problem itself lives in `senior_azure_data_engineer_takehome.docx`. Do not open that document until you have read this one.

---

## The non-negotiables

1. **Strict 4-hour timebox.** Stop at 4 hours. Submit what you have. We discuss this in detail below — it matters.
2. **Fork into your own private Git account.** Do not open a pull request against our repository. Do not push branches to our repository. Details below.
3. **Add your own README in your fork.** It is part of the submission. Details below.
4. **Justify every meaningful decision you make.** Code that runs is not a solution; code that runs and is defended is.

---

## What's in this repo

```
/
├── README.md                                        ← you are here
├── senior_azure_data_engineer_takehome.docx         ← the brief (read after this)
└── data/
    ├── loan_accounts.csv
    ├── loan_transactions.csv
    └── bank_transactions.csv
```

The brief explains the scenario and the four parts of the task. The CSVs are your inputs.

---

## How to submit

We use a **fork-and-keep-private** workflow. This is deliberate. Read the steps carefully.

### Step 1 — Fork this repo into your own Git account

GitHub, GitLab, Bitbucket, Azure DevOps — your choice. Requirements:

- It must be **your own** account, not ours.
- The fork must be **private**. A public repository with our brief in it is a confidentiality breach and we will withdraw you from the process.
- Keep our `README.md`, the brief, and the `data/` folder intact in your fork. We want to see them in the history when we review.

### Step 2 — Do your work in your fork

Commit as you go. Messy intermediate commits are welcome — they tell us how you think. A single squashed commit at the end looks suspicious, not impressive.

### Step 3 — Add your own README in your fork

Your fork must contain a **second README file** that you write — name it `CANDIDATE_README.md` so it does not overwrite ours.

This file is part of the submission. It is how you explain your work to us. It must contain, at minimum, the following sections:

```
# CANDIDATE_README.md

## How to run my code
- Prerequisites (Python version, SQL engine, etc.)
- Step-by-step commands to reproduce my Part A, Part B, and Part C outputs
- Assume a clean machine. If we cannot get your code running in 10 minutes
  we will not score it.

## Repository layout
- Where each part of the answer lives

## Time spent (honest)
- Actual minutes spent on each of the four parts
- Where you went over budget and how you reacted

## Approach and key decisions
For each of the four parts, briefly:
- What approach did you take?
- What alternative did you consider and reject, and why?
- What assumptions did you make?

## Known limitations
- What does not work, is not covered, or is fragile
- What you would fix first if you had more time

## AI tool disclosure
- Which AI tools did you use?
- Where specifically did you use them?
- What did you accept verbatim, and where did you override what they
  suggested? Be concrete.
```

We read `CANDIDATE_README.md` first when we open your fork. If it is missing, thin, or contradicts the code, that is a strong negative signal.

### Step 4 — Give us read access and send the link

When ready:

1. Add the reviewer's email (in your invitation email) as a **read-only collaborator** on your private fork.
2. Reply to the invitation with the URL of the fork.
3. Do **not** open a pull request against our repository. Do **not** push branches to our repository. Do **not** tag us in issues on our repository. We will not look there.

### Why this workflow

It keeps your work cleanly attributed to you in your own Git history; it prevents one candidate's solution from being visible to another; and it removes ambiguity about who owns the code.

---

## The 4-hour timebox

This is the most important rule in the assessment. Read it twice.

**You have 4 hours of working time, total, to complete the exercise.** Not per part. Not "as long as it takes". Four hours.

### Why we enforce it

In the real role you are interviewing for, you will rarely have unlimited time. You will need to make a call about what to deliver in a fixed window and what to defer. We want to see how you make that call.

A candidate who delivers a thoughtful, partial solution in 4 hours scores higher than a candidate who delivers a polished, complete solution in 12 hours. We have no way to verify hours, so the timebox runs on trust. **Inflating the budget to get a better-looking submission is the most common reason strong candidates fail this stage.**

### How to manage the timebox

The brief suggests a split: 75 minutes for Part A, 75 for Part B, 60 for Part C, 30 for Part D. You can rebalance, but stay within the 4-hour total.

A working approach:

1. Start a timer when you begin.
2. When the suggested time for a part is up, stop. Move on. Note what you did not finish.
3. When the 4-hour timer goes, stop entirely. Commit what you have. Write up where you ran out of time in `CANDIDATE_README.md`.
4. If a part is not started at all, do not skip Part D — even a 10-minute reflection write-up is part of the assessment.

If you find you have spare time in the 4 hours, use it to improve `CANDIDATE_README.md` and to justify your decisions more thoroughly. Polish on justification scores higher than a marginal new feature.

---

## What we expect

### A working solution, but more importantly, justified decisions

There are several reasonable answers to every question in this brief. We are not grading you against a specific solution we have in mind. We are grading **whether you can explain why you did what you did**.

Expect us to ask "why?" about any choice you made — in `CANDIDATE_README.md`, in your code comments, and in the follow-up interview. Some examples:

- Why did you pick that join condition?
- Why did you reject the alternative you mentioned?
- Why that tolerance value for amount comparison?
- Why that configuration schema shape?
- Why that data lifecycle for the raw landing zone?
- Why that alerting threshold?

"Because that's how I always do it" is not a justification. "I considered X and Y; I picked X because of Z, and the trade-off is W" is a justification.

If you cannot defend a choice in the follow-up interview, we will assume you did not make it yourself.

### Honesty

- Tell us where things are broken. We would rather you flag it than hope we miss it. We will not miss it.
- Disclose AI tool use. We use them too. Candidates who pretend they did not use AI tools and then cannot explain their own code in the follow-up are an immediate no-hire.
- Be honest about time spent. The timebox runs on trust.

### What we do not expect

- A production-ready system. This is 4 hours of work.
- Polished diagrams. Correct beats beautiful.
- Tests for every function. One small test in Part C, only if you have time.
- That you finish every stretch goal. Stretch goals are not weighted into scoring.
- An Azure subscription. You will not deploy anything. We score design and code.

---

## Confidentiality

The brief, the data, and the scenario are confidential to the recruitment process.

- Do not publish them publicly. Your fork must be private.
- Do not share with other candidates or post on public forums, blogs, social media, or technical Q&A sites.
- The data is synthetic and contains no real customer information, but we ask that you do not redistribute it.

After the process ends — successful or not — you may keep your fork private indefinitely. We just ask that it never becomes public.

---

## Deadline and follow-up

- **Submit within 7 calendar days** of receiving the invitation email.
- Extensions are fine for scheduling reasons (illness, work emergency, etc.). They are not granted to extend the 4-hour working window. Ask before the deadline by replying to your invitation email.
- We aim to respond within 5 working days of submission.
- If we take you forward, you will be invited to a 60-minute walkthrough call. We will go through your work together. Expect questions about *why*, not *what*. That is where the real signal is.
- If we do not take you forward, we will tell you and give you specific feedback rather than a form rejection.

---

## A final note

This exercise is a real sample of the work in the role. The reconciliation problem is the kind of thing that arrives at month-end. The architecture exercise is the kind of conversation that happens in sprint planning. The implementation task is the kind of thing you might be asked to build in your first few weeks.

Treat it as a chance to find out whether this kind of work is what you want to be doing. If it is, we look forward to reading your submission.

Good luck.
