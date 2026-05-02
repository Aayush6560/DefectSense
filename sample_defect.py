def bad(x):
    total = 0
    for i in range(10):
        if i % 2 == 0:
            total += x
        else:
            total -= x
    return total
