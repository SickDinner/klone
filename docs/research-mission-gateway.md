# KLONE 4A.4: Mission Control -tutkimusesikatselun palveluraja

`research_mission_gateway.preview_via_mission_control` on luotetun
Python-palvelun sisäinen, **vain luku** -operaatio.

Ennen esikatselua se vaatii:
1. kutsuvan palvelun toteuttaman käyttäjän tunnistuksen,
2. Hypervisorin salliman `public-room` / `read` -päätöksen,
3. kuratoidun julkisen dossier-aineiston ja paikallisten lähdetavujen
   eheyden tarkistuksen.

Palauttaa käyttöoikeuspäätöksen ja tutkimuksen esikatselun.
Ei luo tietokantaa eikä julkaise väitteitä.

**Tärkeät puutteet:** callback ei yksin todista henkilöllisyyttä;
käyttöliittymän palvelin, istuntohallinta, CSRF-suojaus, auditointiloki,
kutsurajoitukset ja hyväksymistyönkulku on toteutettava erikseen.
Tätä funktiota ei saa altistaa suoraan anonyymille verkkopyynnölle.
