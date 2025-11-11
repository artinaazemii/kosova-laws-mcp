**Kosova Laws MCP**

Kosova Laws MCP është një Model Context Protocol (MCP) server i personalizuar që i mundëson ChatGPT-së dhe sistemeve të tjera të inteligjencës artificiale të kërkojnë, lexojnë dhe analizojnë ligjet zyrtare të Republikës së Kosovës, të publikuara përmes Gazetës Zyrtare të Republikës së Kosovës.

Ky projekt ka për qëllim të bëjë të dhënat ligjore të Kosovës më të qasshme, të kërkueshme dhe të kuptueshme, duke përdorur teknologjitë moderne të AI-së.

**Serveri publik**

Serveri është i hostuar dhe aktiv në këtë adresë publike:
  https://76dc5fd4-c29f-4aa4-a82a-5c57f5132144-00-1z8im0xlygfib.janeway.replit.dev/sse
Ky URL mund të lidhet drejt me ChatGPT përmes funksionit MCP Connector.

**Si të lidhet me ChatGPT**

Për ta përdorur këtë MCP, nevojitet një llogari ChatGPT Plus.
Hapat për konfigurim:
1. Hape ChatGPT (në web ose desktop).
2. Shko te: Settings → App & Connectors → Advanced Settings
3. Aktivizo Developer Mode
(pa këtë hap, nuk do të mund të shtosh MCP servera manualisht).
4. Krijo një lidhje të re (Create Connector) dhe plotëso fushat si më poshtë:
  Name: vendos një emër sipas dëshirës (p.sh. Kosova Laws ose Legal MCP)
  Description: shkruaj një përshkrim të shkurtër (p.sh. Kërkim dhe qasje në ligjet zyrtare të Kosovës)
  URL:
  https://76dc5fd4-c29f-4aa4-a82a-5c57f5132144-00-1z8im0xlygfib.janeway.replit.dev/sse
  (nëse dëshiron të përdorësh serverin “Kosova Laws MCP”, duhet të vendosësh saktësisht këtë link)
  Authentication: zgjidh No authentication
  Kliko Create

Pasi të krijohet lidhja, ChatGPT do të përdorë automatikisht këtë MCP për kërkime në bazën ligjore të Kosovës.

**Shembuj pyetjesh**
Pasi të jetë krijuar lidhja me MCP serverin, përdoruesi mund të parashtrojë pyetje natyrale në gjuhën shqipe, për të kërkuar informacione ligjore nga Gazeta Zyrtare e Republikës së Kosovës.
Disa shembuj:
“Cilat ligje janë publikuar në vitin 2025?”
“Cili ligj e rregullon administratën publike në Republikën e Kosovës?”
“Në cilin ligj trajtohet arsimi i lartë?”


**Shënim**

Ndonjëherë, ChatGPT mund të tentojë të bëjë kërkim në internet në vend që të përdorë MCP-n.
Në atë rast, mjafton t’i thuash:
“Përdor tools te Kosovo Laws MCP (emrin që e vendose tek hapi 4) në vend që të kërkosh në web.”
Pas kësaj, ChatGPT do ta drejtojë pyetjen tek serveri yt MCP dhe do të ofrojë rezultatet zyrtare nga Gazeta Zyrtare.


**Qëllimi i projektit**

Ky projekt është zhvilluar për të demonstruar mënyrën se si inteligjenca artificiale dhe të dhënat publike mund të kombinohen për të përmirësuar qasjen në drejtësi dhe transparencën ligjore.
Duke u lidhur direkt me Gazetën Zyrtare të Republikës së Kosovës, MCP-ja mundëson që çdo qytetar, student apo studiues të marrë informacione të sakta dhe të përditësuara mbi ligjet e vendit përmes një ndërfaqeje inteligjente.
