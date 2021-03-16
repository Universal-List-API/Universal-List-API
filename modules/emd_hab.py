# Extra parsing for markdown (Highlighting and alert boxes)

def parse(rtxt, look, control):
    txtl = rtxt.split(look)
    i, j = 0, 0
    ret_text = ""
    while i < len(txtl):
        if j == 0:
            # This is the start before the specified tag, add it normally
            ret_text += control.start(txtl[i])
            j+=1
        elif j == 1:
            # This is the text we actually want to parse
            ret_text += control.inner(txtl[i])
            j+=1
        else:
            ret_text += control.end(txtl[i])
            j = 1
        i+=1
    return ret_text

class Control():
    def start(self, s):
        return s
    def inner(self, s):
        return s
    def end(self, s):
        return s

class HighlightControl(Control):
    def inner(self, s):
        return "<span class='highlight'>" + s + "</span>"

class BoxControl(Control):
    def inner(self, s):
        style = s.split("\n")[0].strip().replace("<br />", "") # This controls info, alert, danger, warning, error etc...
        if style == "info": # info box
            return "<div class='alert-info white' style='color: white !important;'><i class='fa fa-info-circle i-m3' aria-hidden='true'></i><span class='bold'>Info</span>" + s.replace("info", "", 1) + "</div>"
        return s

# This adds the == highlighter and ::: boxes
def emd(txt: str) -> str:
    # == highlighting
    ret_text = parse(txt, "==", HighlightControl())
    # ::: boxes
    ret_text = parse(ret_text, ":::", BoxControl())
    return ret_text


# Test cases

#emd.emd("Hi ==Highlight== We love you == meow == What about you? == mew == ::: info\nHellow world:::")
