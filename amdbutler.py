import sublime
import sublime_plugin
import os
from . import buffer_parser
from . import crawler
from . import zipper

PATH_SETTING_NAME = 'amd_butler_packages_base_path'
PARAMS_ONE_LINE_SETTING_NAME = 'amd_butler_params_one_line'
SETTINGS_FILE_NAME = 'AmdButler.sublime-settings'


def _all_text(view):
    return view.substr(sublime.Region(0, view.size()))


def _get_sorted_pairs(view):
    try:
        imports_span = buffer_parser.get_imports_span(_all_text(view))
        params_span = buffer_parser.get_params_span(_all_text(view))
        return zipper.zip(view.substr(sublime.Region(*imports_span)),
                          view.substr(sublime.Region(*params_span)))
    except buffer_parser.ParseError as er:
        sublime.error_message(er.message)


def _update_with_pairs(view, edit, pairs):
    imports_span = buffer_parser.get_imports_span(_all_text(view))
    params_span = buffer_parser.get_params_span(_all_text(view))

    project = _get_project_data()
    if (project is not None and
            not project.get('settings', False) is False and
            not project['settings'].get(PARAMS_ONE_LINE_SETTING_NAME, False)
            is False):
        oneLine = project['settings'][PARAMS_ONE_LINE_SETTING_NAME]
    else:
        settings = sublime.load_settings(SETTINGS_FILE_NAME)
        oneLine = settings.get(PARAMS_ONE_LINE_SETTING_NAME)

    # replace params - do these first since they won't affect the
    # imports region
    params_txt = zipper.generate_params_txt(pairs, '\t', oneLine)
    view.replace(edit, sublime.Region(*params_span), params_txt)

    # replace imports
    import_txt = zipper.generate_imports_txt(pairs, '\t')
    view.replace(edit, sublime.Region(*imports_span), import_txt)


def _set_mods(view):
    settings = sublime.load_settings(SETTINGS_FILE_NAME)

    def on_folder_defined(txt):
        project = _get_project_data()
        if project is None:
            # no project open use default setting
            settings.set(PATH_SETTING_NAME, txt)
            sublime.save_settings(SETTINGS_FILE_NAME)
        else:
            project['settings'].update({PATH_SETTING_NAME: txt})
            _save_project_data(project)
        get_imports()

    def get_folder():
        sublime.active_window().show_input_panel(
            'name of folder containing AMD packages (e.g. "src")',
            '', on_folder_defined,
            lambda: None, lambda: None)

    def get_imports():
        _get_available_imports(view)
        view.run_command('amd_butler_add')

    project = _get_project_data()
    if project is not None:
        # create settings project prop if needed
        if (project.get('settings', False) is False or
                project['settings'].get(PATH_SETTING_NAME, False) is False):
            project.update({'settings': {PATH_SETTING_NAME: False}})
            _save_project_data(project)
            get_folder()
        else:
            get_imports()
    else:
        # no project
        if settings.get(PATH_SETTING_NAME, False) is False:
            get_folder()
        else:
            get_imports()


def _get_available_imports(view):
    project = _get_project_data()
    if project is None:
        settings = sublime.load_settings(SETTINGS_FILE_NAME)
        folder_name = settings.get(
            PATH_SETTING_NAME)
        path = _validate_folder(view, folder_name)
        if path is None:
            return
    else:
        settings = project['settings']
        folder_name = settings[PATH_SETTING_NAME]
        path = _validate_folder(view, folder_name)
        if path is None:
            return
    sublime.status_message(
        'AMD Butler: Processing modules in {} ...'.format(path))
    view.mods = crawler.crawl(path, _get_sorted_pairs(view))
    sublime.status_message(
        'AMD Butler: Processing complete. {} total modules processed.'.format(
            len(view.mods)))


def _validate_folder(view, folder_name):
    if view.file_name() is None:
        sublime.error_message('File must be saved in order to '
                              'search for available modules!')
    path = os.path.join(view.file_name().split(folder_name)[0],
                        folder_name)
    if os.path.exists(path):
        return path
    else:
        sublime.error_message('{} not found in the path of the current file!'
                              .format(folder_name))
        return None


def _get_project_data():
    return sublime.active_window().project_data()


def _save_project_data(data):
    return sublime.active_window().set_project_data(data)


class _Enabled(object):
    def is_enabled(self):
        return self.view.settings().get('syntax').find('JavaScript') != -1


class AmdButlerSort(_Enabled, sublime_plugin.TextCommand):
    def run(self, edit):
        _update_with_pairs(self.view, edit, _get_sorted_pairs(self.view))


class AmdButlerAdd(_Enabled, sublime_plugin.TextCommand):
    def run(self, edit):
        if not hasattr(self.view, 'mods'):
            _set_mods(self.view)
        else:
            self.view.window().show_quick_panel(
                self.view.mods, self.on_mod_selected)

    def on_mod_selected(self, i):
        if i != -1:
            pair = self.view.mods.pop(i)
            self.view.run_command('amd_butler_internal_add',
                                  {'pair': pair})


class AmdButlerRemove(_Enabled, sublime_plugin.TextCommand):
    def run(self, edit):
        self.pairs = _get_sorted_pairs(self.view)

        self.view.window().show_quick_panel(
            zipper.scrub_nones(self.pairs), self.on_mod_selected)

    def on_mod_selected(self, i):
        if i != -1:
            pair = self.pairs.pop(i)
            try:
                self.view.mods.append(pair)
            except AttributeError:
                pass
            self.view.run_command('amd_butler_internal_update',
                                  {'pairs': self.pairs})


class AmdButlerInternalUpdate(_Enabled, sublime_plugin.TextCommand):
    def run(self, edit, pairs):
        _update_with_pairs(self.view, edit, pairs)


class AmdButlerInternalAdd(_Enabled, sublime_plugin.TextCommand):
    def run(self, edit, pair=''):
        # add param first
        try:
            params_point = buffer_parser.get_params_span(
                _all_text(self.view))[0]
            self.view.insert(edit, params_point, pair[1] + ',')

            imports_point = buffer_parser.get_imports_span(
                _all_text(self.view))[0]
            self.view.insert(edit, imports_point, '\'{}\','.format(pair[0]))
        except buffer_parser.ParseError as er:
            sublime.error_message(er.message)

        self.view.run_command('amd_butler_sort')


class AmdButlerRefresh(_Enabled, sublime_plugin.TextCommand):
    def run(self, edit):
        _set_mods(self.view)


class AmdButlerPrune(_Enabled, sublime_plugin.TextCommand):
    def run(self, edit):
        pairs = _get_sorted_pairs(self.view)

        new_pairs = buffer_parser.prune(pairs, _all_text(self.view))
        _update_with_pairs(self.view, edit, new_pairs)
