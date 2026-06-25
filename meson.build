project(
  'gator',
  version: '1.4',
  license: 'GPL-3.0-or-later',
  meson_version: '>= 1.0.0',
)

gnome = import('gnome')
i18n = import('i18n')
python = import('python').find_installation('python3', required: true)
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())

# Python sources (installed as a package from src layout)
install_subdir(
  'src/gator',
  install_dir: python.get_install_dir(),
)

# Install a small launcher script so "gator" works from PATH
conf = configuration_data()
conf.set('PYTHON', python.full_path())
conf.set('PKGDATADIR', pkgdatadir)
conf.set('APPID', 'org.gator.Gator')

configure_file(
  input: 'data/gator.in',
  output: 'gator',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

# Data files
install_data(
  'data/org.gator.Gator.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
)

install_data(
  'data/org.gator.Gator.metainfo.xml',
  install_dir: join_paths(get_option('datadir'), 'metainfo'),
)

install_data(
  'data/org.gator.Gator.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps'),
)

install_data(
  'data/org.gator.Gator.gschema.xml',
  install_dir: join_paths(get_option('datadir'), 'glib-2.0', 'schemas'),
)

i18n.gettext(
  'gator',
  preset: 'glib',
)

# Compile schemas / update caches on install (best effort)
gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
