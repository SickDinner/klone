# KLONE 4A.4: Mission Controlin tutkimuspalveluraja

`MissionControlResearchService` on paikallinen palveluadapteri. Se
kytkee 4A.1–4A.3:n tutkimusoperaatiot Hypervisorin julkisen huoneen
käyttöoikeustarkistuksiin ja isäntäpalvelun antamiin tunnistus-,
valtuutus- ja auditointitoimintoihin.

## Operaatiot

- `preview(request, json_text, manifests, source_bytes)`: tarkista
  julkinen aineisto ilman tallennusta.
- `run(request, json_text, manifests, source_bytes)`: tarkista ja
  tallenna versioitu tutkimus.
- `inspect(request, version)`: tarkastele tallennettua versiota.
  Tämä ei tarkista alkuperäisiä lähdetavuja uudelleen.

Kaikki operaatiot vaativat `ResearchServiceRequest`-olion, joka
sisältää principalin, roolin, jäljitystunnuksen ja dossier-tunnuksen.
Pääsy tarkistetaan järjestyksessä: isännän tunnistus, Hypervisor,
isännän resurssikohtainen valtuutus, auditoinnin admission-tapahtuma.

## Turvallisuusrajoitukset

Tämä EI ole HTTP-rajapinta eikä valmis kirjautumisjärjestelmä.
Tunnistus-, valtuutus- ja auditointicallbackit saa antaa vain
luotettu isäntäpalvelu, ei asiakaspyyntö. Palvelu ei julkaise väitteitä
eikä hyväksy tutkimusta automaattisesti.

Tutkimusversion tallennus ja ulkoinen auditointicallback eivät ole
yksi atominen tapahtuma. Jos completion-auditointi epäonnistuu,
tutkimusversio on voitu jo tallentaa. Tuotantovaiheessa tämä
ratkaistaan yhteisellä transaktiolla tai outbox-mallilla.
