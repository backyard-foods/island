def format_string(string, double_size, flip=False):
    char_limit = 15 if double_size else 25
    lines = []
    
    # Split the input string by newlines first
    for input_line in string.split('\n'):
        words = input_line.split()
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= char_limit:
                current_line += " " + word if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
    
    if flip:
        lines.reverse()

    return '\n'.join(lines)
