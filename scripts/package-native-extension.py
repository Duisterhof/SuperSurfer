"""Build an offline-installable VSIX; include only the extension and its runtime dependency."""
import json
from pathlib import Path
import subprocess
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
extension = root / 'native_extension'
manifest = json.loads((extension / 'package.json').read_text())
ws = Path(subprocess.check_output(['node', '-p', "require.resolve('ws/package.json',{paths:[process.argv[1]]})", str(extension)], text=True).strip()).parent
out = root / 'dist' / ('supersurfer-native-' + manifest['version'] + '.vsix')
out.parent.mkdir(exist_ok=True)
xml = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
<Metadata><Identity Language="en-US" Id="{manifest['name']}" Version="{manifest['version']}" Publisher="{manifest['publisher']}"/><DisplayName>SuperSurfer</DisplayName><Description xml:space="preserve">{escape(manifest['description'])}</Description><Tags>agents,workflow</Tags><Categories>Other</Categories><Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="{manifest['engines']['vscode']}"/><Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace"/></Properties><License>extension/LICENSE</License></Metadata>
<Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/>
<Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/><Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true"/></Assets></PackageManifest>'''
with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
    archive.writestr('extension.vsixmanifest', xml)
    archive.writestr('[Content_Types].xml', '''<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="json" ContentType="application/json"/><Default Extension="vsixmanifest" ContentType="text/xml"/><Default Extension="md" ContentType="text/markdown"/><Default Extension="cjs" ContentType="application/javascript"/><Default Extension="js" ContentType="application/javascript"/><Default Extension="svg" ContentType="image/svg+xml"/><Default Extension="css" ContentType="text/css"/><Default Extension="" ContentType="application/octet-stream"/></Types>''')
    for file in extension.rglob('*'):
        rel = file.relative_to(extension)
        if file.is_file() and 'node_modules' not in rel.parts and '__pycache__' not in rel.parts and file.name != 'package-lock.json':
            archive.write(file, 'extension/' + rel.as_posix())
    archive.write(root / 'LICENSE', 'extension/LICENSE')
    for file in ws.rglob('*'):
        if file.is_file(): archive.write(file, 'extension/node_modules/ws/' + file.relative_to(ws).as_posix())
print(out)
