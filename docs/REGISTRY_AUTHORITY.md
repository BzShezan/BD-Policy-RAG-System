# Government authority scope provenance

Registry file: `config/research_sources.json`. Checked 2026-10-19 for added services. These are authority/link checks, not a live-crawl, availability, current-law or content approval claim. The application's crawler was not run during this lookup.

| Scope | Exact roots enabled (plus original `www` matching rule) | Primary authority evidence |
|---|---|---|
| Social Welfare | msw.gov.bd, dss.gov.bd | Existing `reference_pipelines/stage4/REGISTRY_VERIFICATION.md`, checked 2026-10-13 |
| Agriculture | moa.gov.bd, dam.gov.bd | Same original registry verification and official MOA department list |
| Disaster Management | modmr.gov.bd, ddm.gov.bd | Same original registry verification and official MODMR department list |
| Election Commission / NID | ecs.gov.bd, nidw.gov.bd, services.nidw.gov.bd | https://ecs.gov.bd/ explicitly links NID Wing and NID online services; https://www.nidw.gov.bd/enroll_obtaining.php describes enrolment |
| Passports | epassport.gov.bd, dip.gov.bd | https://www.epassport.gov.bd/instructions/instructions ; official e-passport form references DIP: https://www.epassport.gov.bd/api/v1/registrations/download-offline-form |
| Birth/death registration | orgbdr.gov.bd, bdris.gov.bd | Official ORGBDR service link: https://orgbdr.gov.bd/pages/news/6922daef933eb65569e07772 ; official BDRIS portal https://bdris.gov.bd/ |
| Road transport | brta.gov.bd, bsp.brta.gov.bd | BRTA page explicitly directs to BSP: https://brta.gov.bd/index.php/ ; official service portal https://bsp.brta.gov.bd/?lan=en |

Some direct page reads timed out; official search results established the named authority/link relationships. A registry entry never guarantees its server can be read by the local crawler.

The only non-government storage exception is the original MOA/MODMR Oracle host + exact office namespace + fetched government-page referrer/hash proof. No additional storage host, arbitrary subdomain, wildcard `.gov.bd`, external seed, social page, login flow, document mutation or form submission is enabled.

Registry bytes are hashed into every immutable crawl plan and consent. Changed registry bytes invalidate existing scope receipts; issue a fresh request instead of broadening a prior permit.
