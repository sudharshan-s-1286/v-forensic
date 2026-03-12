import os

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# I need to know where the temp files were saved for real.
# Previous writes used `/tmp/vforensic_html.html` which on Windows might map to C:\tmp or something. Let me try retrieving them.
try:
    css_content = read_file('C:/tmp/vforensic_style.css')
except:
    try:
        css_content = read_file('/tmp/vforensic_style.css')
    except:
         css_content = "/* ERROR READING CSS */"
         print("Error reading CSS")

try:
    body_content = read_file('C:/tmp/vforensic_html.html')
except:
    try:
        body_content = read_file('/tmp/vforensic_html.html')
    except:
         body_content = "<!-- ERROR READING HTML -->"
         print("Error reading HTML")

try:
    js_content = read_file('C:/tmp/vforensic_js.js')
except:
    try:
        js_content = read_file('/tmp/vforensic_js.js')
    except:
         js_content = "/* ERROR READING JS */"
         print("Error reading JS")


html_tmpl = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>V-FORENSIC | Corporate Credit Intelligence System</title>
    <!-- CDN Dependencies -->
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
    
    <style>
/* CSS_GOES_HERE */
    </style>
</head>
<body>
    <div id="loading" class="hidden">
        <div class="loading-content">
            <h2 class="space-mono text-center mb-2">ANALYSING<span class="blink">_</span></h2>
            <p id="loading-sub" class="text-dim text-center mb-6">Processing documents...</p>
            <div class="progress-container">
                <div class="progress-sweep"></div>
            </div>
        </div>
    </div>

    <!-- HTML_GOES_HERE -->

    <!-- TOAST_GOES_HERE -->

    <script>
/* JS_GOES_HERE */
    </script>
</body>
</html>"""

out = html_tmpl.replace('/* CSS_GOES_HERE */', css_content).replace('<!-- HTML_GOES_HERE -->\n\n    <!-- TOAST_GOES_HERE -->', body_content).replace('/* JS_GOES_HERE */', js_content)

os.makedirs('e:/IIT HYDERABHAD/v-forensic/frontend', exist_ok=True)
with open('e:/IIT HYDERABHAD/v-forensic/frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(out)
with open('e:/IIT HYDERABHAD/v-forensic/index.html', 'w', encoding='utf-8') as f:
    f.write(out) # Just in case, update the root one as well, but requirement says "frontend/" and "single file html". Wait, plan says frontend/index.html

print("Assembled successfully.")
