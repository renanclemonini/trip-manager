from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Manifest storage that tolerates missing vendor references.

    Some vendored CSS (duralux theme) reference source maps we do not ship.
    Django's post-processing raises ValueError for those references even with
    ``manifest_strict = False``; here the original URL is kept instead so
    ``collectstatic`` never breaks on a missing vendor asset.
    """

    manifest_strict = False

    def url_converter(self, name, hashed_files, template=None):
        converter = super().url_converter(name, hashed_files, template)

        def safe_converter(match):
            try:
                return converter(match)
            except ValueError:
                return match.group(0)

        return safe_converter
