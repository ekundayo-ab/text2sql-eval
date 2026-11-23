# Results

240 runs. Correct answers out of 30 questions:

| model   |   bare |   full |   rag |   rag_fix |
|:--------|-------:|-------:|------:|----------:|
| haiku   |     20 |     29 |    29 |        29 |
| sonnet  |     20 |     30 |    29 |        29 |

## By kind of question (correct answers; questions per kind in brackets)

| kind          |   ('haiku', 'bare') |   ('haiku', 'full') |   ('haiku', 'rag') |   ('haiku', 'rag_fix') |   ('sonnet', 'bare') |   ('sonnet', 'full') |   ('sonnet', 'rag') |   ('sonnet', 'rag_fix') |
|:--------------|--------------------:|--------------------:|-------------------:|-----------------------:|---------------------:|---------------------:|--------------------:|------------------------:|
| aggregate (6) |                   6 |                   6 |                  6 |                      6 |                    6 |                    6 |                   6 |                       6 |
| data (2)      |                   2 |                   2 |                  2 |                      2 |                    2 |                    2 |                   2 |                       2 |
| join (6)      |                   5 |                   6 |                  6 |                      6 |                    5 |                    6 |                   6 |                       6 |
| lookup (2)    |                   2 |                   2 |                  2 |                      2 |                    2 |                    2 |                   2 |                       2 |
| rule (14)     |                   5 |                  13 |                 13 |                     13 |                    5 |                   14 |                  13 |                      13 |

## Average per run

|                       |   input_tokens |   output_tokens |   seconds |   calls |
|:----------------------|---------------:|----------------:|----------:|--------:|
| ('haiku', 'bare')     |        10296.7 |           692.4 |       4.8 |       1 |
| ('haiku', 'full')     |        11163.7 |           555.4 |       4.2 |       1 |
| ('haiku', 'rag')      |        10569.9 |           655   |       4.7 |       1 |
| ('haiku', 'rag_fix')  |        10569.9 |           628.5 |       4.5 |       1 |
| ('sonnet', 'bare')    |        10275.7 |           239.9 |       3.5 |       1 |
| ('sonnet', 'full')    |        11142.7 |           170.6 |       2.9 |       1 |
| ('sonnet', 'rag')     |        10554.6 |           190.3 |       3   |       1 |
| ('sonnet', 'rag_fix') |        10554.6 |           194.1 |       3   |       1 |

## Wrong answers per question

| id   | kind   | wrong in                                                      |
|:-----|:-------|:--------------------------------------------------------------|
| q03  | rule   | haiku/bare, sonnet/bare                                       |
| q04  | rule   | haiku/bare, sonnet/bare                                       |
| q06  | rule   | sonnet/bare, haiku/bare                                       |
| q07  | join   | haiku/bare, sonnet/bare                                       |
| q09  | rule   | haiku/bare, sonnet/bare                                       |
| q11  | rule   | sonnet/bare, haiku/bare                                       |
| q15  | rule   | haiku/bare, sonnet/rag, sonnet/bare, sonnet/rag_fix           |
| q19  | rule   | sonnet/bare, haiku/rag, haiku/full, haiku/rag_fix, haiku/bare |
| q20  | rule   | haiku/bare, sonnet/bare                                       |
| q26  | rule   | sonnet/bare, haiku/bare                                       |
