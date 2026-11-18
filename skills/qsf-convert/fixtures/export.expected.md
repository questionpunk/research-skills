# Commuter study (synthetic)

> embedded: source

## Intro

### welcome [info]
Welcome.

This takes <b>5 minutes</b>.

### commute [single] required
Do you commute to work?

- Yes {code:1}
- Sometimes {code:2}
- No {code:0}

> skip: if "No" -> end of block
> skip: if not "Yes" -> q4

### modes [multi]
How do you travel? Select all

- Car
- Bike & scooter
- Other {text}
- None {exclusive}

> randomize: options
> show if: commute is "Yes" or commute is "Sometimes"

---

### q4 [text]
How many minutes is your commute?

<!-- unsupported skip logic on q4: If How many minutes is your commute? Is Empty, Then Skip To End of Survey -->

## Ratings

### agree [matrix]
How much do you agree?

Rows:
- My commute is reliable {var:agree_reliable}
- My commute is cheap {var:agree_cheap}

Columns:
- Disagree
- Neutral
- Agree

### nps [nps] request
How likely are you to recommend your commute?

<!-- unsupported display logic on nps: If source Is Equal to panel -->

### overall [slider]
Rate your commute overall.

- Overall

### sbs_1 [matrix] required
Compare the two routes
Speed

Rows:
- Route A
- Route B

Columns:
- Slow
- Fast

### sbs_2 [matrix-multi]
Compare the two routes
Comfort

Rows:
- Route A
- Route B

Columns:
- Poor
- Good

<!-- unsupported question QID10 (timer): type Timing/PageTimer is outside the supported set: Timing -->

<!-- unsupported flow: branch starts, only when: If source Is Equal to panel -->

## Follow-up

### Q2_other [essay]
Anything else?

### q12 [dropdown]
Which city?

- Lisbon
- Porto

### hours [matrix-text]
How many hours per week?

Rows:
- Working
- Commuting

Columns:
- Hours

### contact [form]
How can we reach you?

- Name
- Phone

### split [sum]
Split 100 points between the modes.

- Car
- Bike

> total: 100
> randomize: options

<!-- unsupported flow: end of survey -->

<!-- flow: Branch ends -->
