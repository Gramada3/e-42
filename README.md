# E-42 (personal) – integrare Home Assistant

Integrare proprie, scrisă de la zero, care citește contul tău e-bloc.ro direct, fără alt server intermediar și fără licență.

## Ce oferă (v0.1.0)

Pentru fiecare apartament din cont se creează un dispozitiv cu senzorii:

| Senzor | Descriere |
|---|---|
| De plată | Suma curentă de plată (RON), cu cod client, proprietar și nr. persoane ca atribute |
| Scadență | Data scadenței |
| Luna afișată | Luna listei de plată și perioada de citire a indecșilor |
| Ultima plată | Suma ultimei plăți, cu data și istoricul ultimelor 12 plăți |
| Index &lt;contor&gt; | Câte un senzor pentru fiecare contor (apă rece/caldă și gaz în m³, energie în kWh) |

Senzorii de contoare sunt compatibili cu panoul **Energie** din Home Assistant.

## Trimiterea indecșilor (v0.2.0)

**Din interfață:** fiecare contor are un câmp **Index nou …**. Completezi valorile, care rămân doar în Home Assistant, apoi apeși butonul **Trimite indecșii** al apartamentului. Abia atunci se trimit toate odată la e-bloc.ro.

**Din automatizări:** folosește acțiunea `ebloc_personal.trimite_index`:

```yaml
action: ebloc_personal.trimite_index
data:
  entity_id: sensor.asoc_bloc_a_ap_7_index_apa_rece_baie
  valoare: 130.25
```

Înainte de trimitere se verifică două lucruri:
- asociația trebuie să accepte indecși în acel moment (senzorul **Luna afișată** arată perioada și atributul `se_pot_trimite_indecsi`);
- indexul nou nu poate fi mai mic decât cel vechi.

Dacă o condiție nu e îndeplinită, apare o eroare cu motivul și nu se trimite nimic. După o trimitere reușită, datele se reîmprospătează automat.

## Instalare

**Manual:** copiază folderul `custom_components/ebloc_personal` în folderul `config/custom_components/` al Home Assistant, apoi repornește Home Assistant.

**HACS (repo propriu):** urcă acest folder într-un repository GitHub al tău, apoi în HACS → ⋮ → *Custom repositories* adaugă URL-ul, cu tipul *Integration*.

## Configurare

1. **Setări → Dispozitive și servicii → Adaugă integrare → E-bloc (personal)**
2. Introdu emailul și parola de la e-bloc.ro.
3. Opțional, din **Configurare**, poți schimba intervalul de actualizare (implicit 6 ore, între 1 și 24).

Dacă îți schimbi parola, Home Assistant îți cere automat parola nouă.

## Note

- Folosește același API ca aplicația mobilă e-bloc.ro. API-ul nu este documentat public, deci poate fi schimbat de e-bloc fără anunț.
- Parola rămâne doar în Home Assistant. Spre e-bloc.ro se trimite doar hash-ul SHA-512, la fel ca în aplicația oficială.
- Poate rula în paralel cu integrarea „E-bloc România” a altui autor, pentru că are un domeniu diferit (`ebloc_personal`).
