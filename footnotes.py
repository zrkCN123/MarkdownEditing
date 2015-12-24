import sublime
import sublime_plugin
import re

DEFINITION_KEY = 'MarkdownEditing-footnote-definitions'
REFERENCE_KEY = 'MarkdownEditing-footnote-references'
REFERENCE_REGEX = "\[\^([^\]]*)\]"
DEFINITION_REGEX = "^ *\[\^([^\]]*)\]:"


def get_footnote_references(view):
    ids = {}
    for ref in view.get_regions(REFERENCE_KEY):
        if not re.match(DEFINITION_REGEX, view.substr(view.line(ref))):
            id = view.substr(ref)[2:-1]
            if id in ids:
                ids[id].append(ref)
            else:
                ids[id] = [ref]
    return ids


def get_footnote_definition_markers(view):
    ids = {}
    for defn in view.get_regions(DEFINITION_KEY):
        id = view.substr(defn).strip()[2:-2]
        ids[id] = defn
    return ids


def get_footnote_identifiers(view):
    ids = list(get_footnote_references(view).keys())
    ids.sort()
    return ids


def get_last_footnote_marker(view):
    ids = sorted([int(a) for a in get_footnote_identifiers(view) if a.isdigit()])
    if len(ids):
        return int(ids[-1])
    else:
        return 0


def get_next_footnote_marker(view):
    return get_last_footnote_marker(view) + 1


def is_footnote_definition(view):
    line = view.substr(view.line(view.sel()[-1]))
    return re.match(DEFINITION_REGEX, line)


def is_footnote_reference(view):
    refs = view.get_regions(REFERENCE_KEY)
    for ref in refs:
        if ref.contains(view.sel()[0]):
            return True
    return False


def strip_trailing_whitespace(view, edit):
    tws = view.find('\s+\Z', 0)
    if tws:
        view.erase(edit, tws)

def view_is_markdown(view):
    if len(view.sel()) > 0:
        return bool(view.score_selector(view.sel()[0].a, "text.html.markdown"))
    else:
        return False

class MarkFootnotes(sublime_plugin.EventListener):
    def update_footnote_data(self, view):
        if view_is_markdown(view):
            view.add_regions(REFERENCE_KEY, view.find_all(REFERENCE_REGEX), '', 'cross', sublime.HIDDEN)
            view.add_regions(DEFINITION_KEY, view.find_all(DEFINITION_REGEX), '', 'cross', sublime.HIDDEN)

    def on_modified_async(self, view):
        self.update_footnote_data(view)

    def on_load(self, view):
        self.update_footnote_data(view)


class GatherMissingFootnotesCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        refs = get_footnote_identifiers(self.view)
        defs = get_footnote_definition_markers(self.view)
        missingnotes = [note_token for note_token in refs if not note_token in defs]
        if len(missingnotes):
            self.view.insert(edit, self.view.size(), "\n")
            for note in missingnotes:
                self.view.insert(edit, self.view.size(), '\n [^%s]: ' % note)

    def is_enabled(self):
        return bool(self.view.score_selector(self.view.sel()[0].a, "text.html.markdown"))

def suggest_default_link_name(title):
    # Camel case impl.
    ret = ''
    for word in title.split():
      ret += word.capitalize()
      if len(ret) > 30:
        break
    return ret

class InsertFootnoteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        sel = view.sel()[-1]
        startloc = sel.end()
        if len(sel) > 0:
            markernum = suggest_default_link_name(view.substr(sel))
        else:
            markernum = get_next_footnote_marker(view)
        if bool(view.size()):
            targetloc = view.find('(\s|$)', startloc).begin()
        else:
            targetloc = 0
        view.insert(edit, targetloc, '[^%s]' % markernum)
        view.insert(edit, view.size(), '\n [^%s]: ' % markernum)
        view.run_command('set_motion', {"inclusive": True, "motion": "move_to", "motion_args": {"extend": True, "to": "eof"}})
        if view.settings().get('command_mode'):
            view.run_command('enter_insert_mode', {"insert_command": "move", "insert_args": {"by": "characters", "forward": True}})

    def is_enabled(self):
        return bool(self.view.score_selector(self.view.sel()[0].a, "text.html.markdown"))


class GoToFootnoteDefinitionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        defs = get_footnote_definition_markers(self.view)
        regions = self.view.get_regions(REFERENCE_KEY)

        sel = self.view.sel()
        if len(sel) == 1:
            target = None
            selreg = sel[0]

            for region in regions:
                if selreg.intersects(region):
                    target = self.view.substr(region)[2:-1]
            if not target:
                try:
                    target = self.view.substr(self.view.find(REFERENCE_REGEX, sel[-1].end()))[2:-1]
                except:
                    pass
            if target:
                self.view.sel().clear()
                self.view.sel().add(defs[target])
                self.view.show(defs[target])

    def is_enabled(self):
        return bool(self.view.score_selector(self.view.sel()[0].a, "text.html.markdown"))


class GoToFootnoteReferenceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        refs = get_footnote_references(self.view)
        match = is_footnote_definition(self.view)
        if match:
            target = match.groups()[0]
            self.view.sel().clear()
            [self.view.sel().add(a) for a in refs[target]]
            self.view.show(refs[target][0])

    def is_enabled(self):
        return bool(self.view.score_selector(self.view.sel()[0].a, "text.html.markdown"))


class MagicFootnotesCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if (is_footnote_definition(self.view)):
            self.view.run_command('go_to_footnote_reference')
        elif (is_footnote_reference(self.view)):
            self.view.run_command('go_to_footnote_definition')
        else:
            self.view.run_command('insert_footnote')

    def is_enabled(self):
        return bool(self.view.score_selector(self.view.sel()[0].a, "text.html.markdown"))


class SwitchToFromFootnoteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if (is_footnote_definition(self.view)):
            self.view.run_command('go_to_footnote_reference')
        else:
            self.view.run_command('go_to_footnote_definition')

    def is_enabled(self):
        return bool(self.view.score_selector(self.view.sel()[0].a, "text.html.markdown"))


class SortFootnotesCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        strip_trailing_whitespace(self.view, edit)
        defs = get_footnote_definition_markers(self.view)
        notes = {}
        erase = []
        keyorder = map(lambda x: self.view.substr(x)[2:-1], self.view.get_regions(REFERENCE_KEY))
        keys = []
        [keys.append(r) for r in keyorder if not r in keys]

        for (key, item) in defs.items():
            fnend = self.view.find('(\s*\Z|\n\s*\n(?!\ {4,}))', item.end())
            fnreg = sublime.Region(item.begin(), fnend.end())
            notes[key] = self.view.substr(fnreg).strip()
            erase.append(fnreg)
        erase.sort()
        erase.reverse()
        [self.view.erase(edit, reg) for reg in erase]

        for key in keys:
            self.view.insert(edit, self.view.size(), '\n\n ' + notes[key])

    def is_enabled(self):
        return bool(self.view.score_selector(self.view.sel()[0].a, "text.html.markdown"))
