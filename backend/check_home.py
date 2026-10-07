import re
html = open(r'C:\Users\haseeb\.local\share\kilo\tool-output\home.html').read()
print('Length:', len(html))
print('Has root div:', 'id="__next"' in html or 'root' in html.lower())
print('Has script tags:', len(re.findall(r'<script', html)))
