Official JobAdder API v2 OpenAPI reference supplied by the user.
Primary live docs: https://api.jobadder.com/v2/docs
Use this schema before inferring or guessing JobAdder request/response models.

Corrected salary/notice source of truth: references/salary_notice_logic_handover.md
Core rule: (monthly base × guaranteed salary months ÷ 12) + fixed recurring monthly allowances.
AWS is a guaranteed 13th-month salary component. Support 13, 13.5, 14 and 14.5 salary months.
Exclude variable/discretionary bonus, statutory contributions, commission, claims and non-cash benefits.
