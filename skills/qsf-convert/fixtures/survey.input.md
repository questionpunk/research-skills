# Product feedback pulse

<!-- Synthetic fixture: every supported question type, both rules and a page break. -->

## Screener

### used [single] required
Have you used the product in the last 30 days?

- Yes
- No
- Not sure

> skip: if "No" -> end of survey
> skip: if "Not sure" -> role

### features [multi] request
Which features did you use?
Select all that apply.

- Reports & exports
- Sharing
- Other {text}
- None of these {exclusive}

> show if: used is "Yes"

### role [dropdown]
What is your role?

- Researcher
- Product manager
- Designer

---

### intro [info]
The next questions are about your <strong>overall</strong> experience.

## Experience

### nps [nps] required
How likely are you to recommend the product to a colleague?

### agree [matrix]
How much do you agree with each statement?

Rows:
- It is easy to use
- It saves me time

Columns:
- Disagree
- Neither
- Agree

### often [matrix-multi]
When do you use each part?

Rows:
- Reports
- Sharing

Columns:
- Weekdays
- Weekends

### effort [slider]
How much effort did setup take?

- Setup

> range: 1 to 7
> labels: Very little | A great deal

### priorities [rank]
Rank what we should improve first.

- Speed
- Price < value
- Support

### why [text-long]
Why did you give that score?

> show if: used is "Yes" or role is not "Designer"

### email [text]
Your work email

### story [essay]
Tell us about the last time the product let you down.
