s="sagardadawillgetnewjobthisyear"

# def reverse(s):
#     reverse=""
#     return s[::-1]

# print (reverse(s))

# def reverse(s):
#     reverse=""
#     for i in range(len(s) -1,-1,-1):
#         reverse += s[i]
#     return reverse

# print (reverse(s))

def reverse_string(s):
    result = ""
    for char in s:
        result = char + result
    return result 
print(reverse_string(s))  

