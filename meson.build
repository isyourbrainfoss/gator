project(
  'croc-gui',
  version: '1.2',
  license: 'GPL-3.0-or-later',
  meson_version: '>= 0.64.0',
)

gnome = import('gnome')
python = import('python3').find_installation('python3', required: true)
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())

# Python sources (installed as a package)
install_subdir(
  '.',
  install_dir: python.get_install_dir(),
  exclude_files: [
    'meson.build',
    'TASKS.md',
    'AGENTS.md',
    'README.md',
    'pyproject.toml',
    'data',
    'tests',
    '.gitignore',
  ],
  exclude_directories: [
    '__pycache__',
    'croc_gui.egg-info',
    'tests',
    'data',
    '.git',
  ],
)

# Install a small launcher script so "croc-gui" works from PATH
conf = configuration_data()
conf.set('PYTHON', python.full_path())
conf.set('PKGDATADIR', pkgdatadir)
conf.set('APPID', 'org.croc.CrocGUI')

configure_file(
  input: 'data/croc-gui.in',
  output: 'croc-gui',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

# Data files
install_data(
  'data/org.croc.CrocGUI.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)

install_data(
  'data/org.croc.CrocGUI.metainfo.xml',
  install_dir: join_paths(get_option('datadir'), 'metainfo'),
)

install_data(
  'data/org.croc.CrocGUI.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'),
)

install_data(
  'data/org.croc.CrocGUI.gschema.xml',
  install_dir: join_paths(get_option('datadir'), 'glib-2.0', 'schemas'),
)

# Compile schemas / update caches on install (best effort)
gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
