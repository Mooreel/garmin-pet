function codexText(value) {
    if (value == null) {
        return "";
    }
    return value.toString();
}

function codexTextEquals(value, expected) {
    return codexText(value).equals(expected);
}

function codexTextStartsWith(value, prefix) {
    var text = codexText(value);
    if (text.length() < prefix.length()) {
        return false;
    }
    return text.substring(0, prefix.length()).equals(prefix);
}
