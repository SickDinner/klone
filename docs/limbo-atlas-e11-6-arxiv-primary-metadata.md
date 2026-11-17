# KLONE E11.6 – versionumeroitu arXiv-metatietotosite

## Lähtötilanne: E11.5 toteutui Androidilla

Termuxin 17.11.2026 todellisessa ajossa 56/56 kohdennettua testiä
läpäistiin ja tutkimusparille 26/24 syntyi:
- **10** alkuperäislähteestä varmennusta odottavaa kontekstikatkelmaa
- **6** sivuun siirrettyä otsikkoa, kysymystä tai toimituksellista varoitusta
- **20** keskeneräistä Council72-tarkistustehtäväehdotusta
- **0** toteutunutta riippumatonta tutkimus- tai Council72-arviointia
- **0** päämuistikirjoitusta

Tarkistusjonon paikallinen nimi:
\`~/klone-var/e11/e11-5-tarkistusjono-20261117-042347.json\`.

## Mikä E11.6 oikeasti on

\`src/klone/limbo_arxiv_primary.py\` käsittelee ainoastaan
E10:n ajantasaisesta kanonisesta, julkisesta tutkimusparista
tunnistetut versionumeroidut \`https://arxiv.org/abs/<ID>v<N>\`-URL:t.

**Tarkistamaton teksti ei muutu varmennetuksi vain siksi,
että se muistuttaa tutkimuksen otsikkoa.** E11.6 hakee
arXivin virallisesta Atom-metatietorajapinnasta version,
otsikon, bibliografiset aikaleimat ja **alkuperäisen
julkaisun tiivistelmän**. Se tallentaa saadulle vastaukselle
SHA-256-tarkisteen, tiivistelmän tarkisteen ja kirjauksen
mahdollisesta otsikko-/lähde-ID-täsmäyksestä Memory Coreen.

**Se ei hae tutkimusten PDF:iä eikä kokotekstejä.
Se ei arvioi riippumatonta toistettavuutta tai väitteen totuutta.**

### Android/Termux – ensin ilman verkkoa

\`\`\`bash
cd ~/klone-arxiv-e1 &&
git fetch origin feat/limbo-external-intelligence-20261115 &&
git switch --detach FETCH_HEAD &&
bash scripts/klone-e11-6-phone.sh
\`\`\`

Skripti ajaa kohdennetut tutkimusregressiot ja muodostaa
E11.6:n **offline-suunnitelman**.
Verkkopyyntöjä ei tehdä.

### Vapaaehtoinen nimenomainen verkkolupa

ArXivin julkisten Atom-julkaisumetatietojen hakeminen
onnistuu tämän jälkeen komennolla:

\`\`\`bash
cd ~/klone-arxiv-e1
bash scripts/klone-e11-6-phone.sh --fetch
\`\`\`

Skripti kysyy kirjoittamaan täsmälleen
**HYVAKSY ARXIV**. Muulla vastauksella se keskeyttää.

Hyväksytyssä ajossa ohjelma lähettää **yhden**
julkisen HTTPS GET -pyynnön osoitteeseen,
joka on muodostettu vain E10:n hyväksytyistä
versionumeroiduista arXiv-tunnuksista.
Verkkopalvelimet, PDF:t tai käyttäjän itse antamat
URL-parametrit eivät ole sallittuja.

Haku voi epäonnistua esimerkiksi arXivin
tilapäisen palveluhäiriön, pääsynrajoituksen tai
julkaisuversion puuttumisen vuoksi. Tällöin se
keskeyttää, eikä keksitystä tai osittaisesta
aineistosta tehdä tutkimustositetta.

### E11.6:n turvallisuusrajat

- Ilman kahta julkaisua, joilla molemmilla on
  \`arxiv.org/abs/2611....vN\`-muotoinen HTTPS-polku,
  vaihe hylkää syötteen.
- Ei mielivaltaisia URL-osoitteita, isäntänimiä,
  IP-numeroita, HTTP-uudelleenohjauksia, välityspalvelimia
  tai käyttäjän itse rakentamia lisäparametreja.
- Yksi Atom-haku kahdelle arXiv-tunnukselle,
  enimmäisvastauksen koko 256 KiB, rajatut tekstikentät.
- Molempien saatujen Atom-julkaisu-ID:iden pitää vastata
  täsmälleen alkuperäisen lähteen **versiota**.
  Väärä versio, puuttuva julkaisu ja XML/DTD-virhe hylätään.
- JSON-raportin täsmäytys erottaa
  \`title_matches_memory\` ja
  \`scientific_truth_verified=false\` toisistaan.
- Kaikki raportit ovat uusia, eivätkä ylikirjoita vanhoja.
- Päämuistia, E7-päiväkirjaa, tutkimushuoneita, 8000/8031/8041
  -palvelimia, Council72-äänestyksiä tai agenttien
  oikeuksia muuteta.

### Sen jälkeen: E11.7 – oikea tiivistelmä- ja selostusvertailu

E11.6:n tulokset muodostavat mahdollisuuden verrata,
onko käyttäjälle aiemmin laaditussa selostuksessa
väitetyille avainhavainnoille todellinen vastine
arXivin julkaisutiivistelmässä.

Vertailu tulee silti raportoida vain
**tiivistelmien kontekstiosumiksi**, ellei
alkuperäinen täysi julkaisuteksti, menetelmät ja
mittausaineisto ole erikseen tarkastettu.
