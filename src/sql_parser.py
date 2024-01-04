from string import digits

from pyparsing import (
    CaselessKeyword,
    Combine,
    Forward,
    Group,
    Literal,
    Optional,
    Or,
    ParserElement,
    Word,
    alphas,
    alphanums,
    delimitedList,
    nums,
    oneOf,
    quotedString,
    string,
)


ParserElement.setDefaultWhitespaceChars(" \t\r")


select_stmt = Forward()
keywords = "SELECT FROM WHERE JOIN ON ORDER BY LIMIT OFFSET GROUP HAVING AS".split()
SELECT, FROM, WHERE, JOIN, ON, ORDER, BY, LIMIT, OFFSET, GROUP, HAVING, AS = (
    map(CaselessKeyword, keywords)
)
keyword = Or(CaselessKeyword(kw) for kw in keywords)
punctuation = [
    "(",
    ")",
    ", ",
    "*",
]
LPAR, RPAR, COMMA, STAR = map(Word, punctuation)

identifier = (~keyword + Word(alphas, alphanums + "_$")).setName("identifier")

column = delimitedList(identifier, ".", combine=True)

function_name = Word(alphas, alphanums + "_")
function_arg = (STAR | identifier)
function_call = Group(function_name + LPAR + Optional(delimitedList(function_arg)) + RPAR)

column_name = (function_call | column).setName("column name")
table_name = identifier.setName("table name")

alias = Optional(AS.suppress() + identifier).setName("alias")
table_alias = Optional(identifier)
column_def = Group(column_name + alias)
columns = Group(delimitedList(column_def)) | STAR
table = Group(table_name + table_alias)

sign = oneOf("+ -")

non_zero_digit = Word(digits.replace("0", ""), exact=1)
zero = Word("0", exact=1)
any_digit = Word(digits)
number = (zero | Combine(non_zero_digit + Optional(any_digit)))
integer = Combine(Optional(sign) + number)

decimal_point = Literal(".")
real = Combine(
    Optional(sign)
    + (
        (any_digit + Optional(decimal_point + Optional(any_digit)))
        | (decimal_point + any_digit)
    )
)

lhs = column_name
rhs = real | integer | quotedString | column_name
comparison_operator = oneOf("= != < > >= <= <> LIKE ILIKE")
condition = Group(lhs + comparison_operator + rhs)
logical_op = oneOf("AND OR")

sorting_option = oneOf("ASC DESC", caseless=True)

expr = Forward()
expr <<= condition + Optional(logical_op + expr)  # recursive definition


JOIN_CLAUSE = Optional(
    Group(
        JOIN
        + table_name("join_table")
        + Optional(table_alias)("join_alias")
        + ON
        + expr("join_condition")
    ).setName("JOIN_CLAUSE"),
)
WHERE_CLAUSE = Optional(
    Group(
        WHERE
        + expr
    ),
).setName("WHERE_CLAUSE")
GROUPBY_CLAUSE = Optional(
    Group(
        GROUP
        + BY
        + Group(
            delimitedList(column_name)
        )
    ),
)
HAVING_CLAUSE = Optional(
    Group(
        HAVING
        + Group(expr)
    ),
)
ORDERBY_CLAUSE = Optional(
    Group(
        ORDER
        + BY
        + Group(
            delimitedList(
                column_name
                + Optional(sorting_option)
            )
        )
    ),
)
LIMIT_CLAUSE = Optional(LIMIT + integer)
OFFSET_CLAUSE = Optional(OFFSET + integer)


select_stmt << (
    SELECT
    + columns
    + FROM
    + table
    + JOIN_CLAUSE
    + WHERE_CLAUSE
    + GROUPBY_CLAUSE
    + HAVING_CLAUSE
    + ORDERBY_CLAUSE
    + LIMIT_CLAUSE
    + OFFSET_CLAUSE
)


def debug_parser(parser):
    parser.setDebug()
    parser.setFailAction(lambda s, l, e: print("Failed at:", s[l:e]))


example_queries = [
    "SELECT name, age FROM users",
    "SELECT id, COUNT(*) FROM orders GROUP BY id",
    "SELECT * FROM products WHERE price > 100",
    "SELECT employeeId, department FROM employees WHERE salary >= 50000 AND department = 'HR'",
    "SELECT a, b FROM table1 JOIN table2 ON table1.id = table2.ref_id",
    "SELECT title FROM books ORDER BY published_date DESC LIMIT 5",
    "SELECT user_id, SUM(amount) FROM transactions GROUP BY user_id HAVING SUM(amount) > 1000",
    "SELECT name FROM customers WHERE age > 30 AND region = 'Europe' ORDER BY name",
    "SELECT product, category, price FROM inventory WHERE stock > 0 AND price < 500 ORDER BY price DESC LIMIT 10 OFFSET 5",
    "SELECT a.name, b.department FROM employees a JOIN departments b ON a.dept_id = b.id WHERE a.experience > 5"
]


for example in example_queries:
    parsed = select_stmt.parseString(example)
    print(parsed)
    # print(parsed.dump())
