import os
import re

RESERVED_WORDS = ['string', 'window']
sep = re.escape(os.sep)
skip = re.compile('{0}(nls|tests)($|{0})'.format(sep))


def crawl(path):
    mods = []
    print(skip)
    for package in os.listdir(path):
        for root, dirs, files in os.walk(os.path.join(path, package)):
            print(root)
            print(dirs)
            if skip.search(root) is None:
                print(files)
                for f in files:
                    if f.endswith('.js'):
                        name = f[:-3]
                        paramName = get_param_name(name, package)
                        base = root.replace(path + '/', '')
                        mods.append(('{}/{}'.format(base, name), paramName))
    print(mods)
    return mods


def get_param_name(name, package):
    if name in RESERVED_WORDS:
        return package + name.title()
    elif name.find('-') != -1:
        words = name.split('-')
        return words[0] + words[1].title()
    else:
        return name
