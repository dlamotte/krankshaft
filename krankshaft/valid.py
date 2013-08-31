# TODO helpful validators
#   - email
#   - int_range(start, end) -> validator(value) -> value or raise ValueError
#
#
# Pattern:
#   raise ValueError when value is not accepted
#   return value otherwise (can value be transformed? yes, '1' -> 1 [string to int])
#
#
# expect() does the heavy lifting of deciding if we have a validator or
# simply a type to check...
