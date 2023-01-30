def pairwise(iterable):
    "s -> (s0, s1), (s2, s3), (s4, s5), ..."
    a = iter(iterable)
    return zip(a, a)

def split_list(input_list,n):
    first_half=input_list[:n]
    sec_half=input_list[n:]
    return first_half,sec_half
