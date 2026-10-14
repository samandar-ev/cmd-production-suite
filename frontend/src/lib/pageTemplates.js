import { lang } from './i18n';
import * as ru from './pageTemplates.ru';

const line = (v, fallback) => (v && v.trim()) || fallback;

const enStrategyBody = ({ goal, audience, platforms, branding } = {}) => `# Content Strategy

## Business goal
${line(goal, 'What does success look like for this client in 3–6 months?')}

## Target audience
${line(audience, 'Who we are trying to reach: demographics, interests, pain points, where they spend time online.')}

## Platforms & posting frequency
${line(platforms, '- Instagram: 3 reels / week\n- TikTok: 4 videos / week')}

## Content pillars
- Education: tips and how-tos
- Behind the scenes: team, process, craft
- Social proof: testimonials, results, UGC
- Promotion: offers and launches (max 20%)

## Tone of voice
Friendly, confident, no jargon.

## Visual branding
${line(branding, 'Colors, fonts, look & feel, references, things to avoid.')}

## Best posting times
- Weekdays 18:00–21:00
- Weekends 10:00–13:00

## KPIs
- [ ] Reach / views per month:
- [ ] Engagement rate:
- [ ] Follower growth:
- [ ] Leads / sales from social:

## Notes
`;

const EN_TEMPLATES = [
  {
    id: 'strategy',
    name: 'Content Strategy',
    icon: '🎯',
    description: 'Goals, audience, pillars, platforms and KPIs for a client.',
    body: enStrategyBody(),
  },
  {
    id: 'brief',
    name: 'Client Brief',
    icon: '📋',
    description: 'Onboarding questionnaire to fill in with a new client.',
    body: `# Client Brief

## About the business
- Company / brand:
- Website & social handles:
- Products or services to promote:
- What makes them different:

## Goals
- Main goal for this project:
- How we will measure success:

## Audience
- Ideal customer:
- Their problems and desires:

## Competitors
-

## Brand
- Tone of voice:
- Colors / fonts / logo files:
- Do's and don'ts:

## Logistics
- Main contact & approval process:
- Budget:
- Key dates / deadlines:
- Assets the client provides:

## Checklist
- [ ] Access to social accounts
- [ ] Brand assets received
- [ ] Contract signed
- [ ] Kick-off call done
`,
  },
  {
    id: 'shoot',
    name: 'Shoot Plan',
    icon: '🎬',
    description: 'Call sheet and shot list for a production day.',
    body: `# Shoot Plan

## Details
- Date & call time:
- Location / address:
- Client contact on set:
- Crew:
- Talent:

## Schedule
- 09:00 Arrive & set up
- 10:00 Shots 1–5
- 13:00 Lunch
- 14:00 Shots 6–10
- 17:00 Wrap

## Shot list
1. Wide establishing shot of location
2. Product close-ups (3 angles)
3. Talent intro to camera
4. B-roll: hands, process, details
5. Vertical versions for reels

## Gear
- [ ] Cameras & lenses
- [ ] Batteries & cards (charged / formatted)
- [ ] Audio (lav + shotgun)
- [ ] Lights & stands
- [ ] Gimbal / tripod

## Notes
`,
  },
  {
    id: 'script',
    name: 'Video Script',
    icon: '✍️',
    description: 'Hook, body and call to action for a short-form video.',
    body: `# Video Script

- Platform & format: Reel, 30–45 s, 9:16
- Goal:
- Pillar:

## Hook (0–3 s)
> The first line that stops the scroll.

## Body
1. Point one
2. Point two
3. Point three

## Call to action
> Follow for more / Book a call / Link in bio

## On-screen text & captions
-

## Visual notes / B-roll
-

## Caption & hashtags
`,
  },
  {
    id: 'calendar',
    name: 'Monthly Content Plan',
    icon: '🗓️',
    description: 'Week-by-week plan of posts for one month.',
    body: `# Content Plan: Month

## Focus this month
Theme, launch or campaign to push.

## Week 1
- [ ] Mon: Reel, Education:
- [ ] Wed: Carousel, Social proof:
- [ ] Fri: Reel, Behind the scenes:

## Week 2
- [ ] Mon:
- [ ] Wed:
- [ ] Fri:

## Week 3
- [ ] Mon:
- [ ] Wed:
- [ ] Fri:

## Week 4
- [ ] Mon:
- [ ] Wed:
- [ ] Fri:

## Key dates
-
`,
  },
  {
    id: 'campaign',
    name: 'Campaign Plan',
    icon: '📣',
    description: 'Launch or ad campaign: offer, channels, budget, timeline.',
    body: `# Campaign Plan

## Overview
- Campaign name:
- Objective: awareness / leads / sales
- Offer:
- Dates:

## Audience & targeting
-

## Key message
> One sentence the audience should remember.

## Channels & budget
- Instagram / Facebook ads:
- TikTok ads:
- Organic posts:
- Email / influencers:

## Creatives needed
- [ ] Hero video (16:9 + 9:16)
- [ ] 3 short cut-downs
- [ ] Static ads
- [ ] Landing page

## Timeline
1. Brief & concepts
2. Production
3. Client approval
4. Launch
5. Optimise & report

## KPIs & targets
-
`,
  },
  {
    id: 'report',
    name: 'Monthly Report',
    icon: '📊',
    description: 'Results, wins and next steps to send to the client.',
    body: `# Monthly Report

## Summary
Two or three sentences: how the month went.

## Results
- Posts published:
- Total views / reach:
- Engagement rate:
- Follower growth:
- Leads / sales:

## Top performing content
1.
2.
3.

## What worked
-

## What didn't
-

## Plan for next month
- [ ]
`,
  },
  {
    id: 'meeting',
    name: 'Meeting Notes',
    icon: '🤝',
    description: 'Agenda, decisions and action items.',
    body: `# Meeting Notes

- Date:
- Attendees:

## Agenda
1.

## Notes
-

## Decisions
-

## Action items
- [ ] Who: what, by when
`,
  },
  {
    id: 'competitors',
    name: 'Competitor Analysis',
    icon: '🔍',
    description: 'What competitors post, what works, and gaps to own.',
    body: `# Competitor Analysis

## Competitor 1
- Handle / website:
- Followers & posting frequency:
- Content that performs best:
- Strengths:
- Weaknesses:

## Competitor 2
- Handle / website:
- Followers & posting frequency:
- Content that performs best:
- Strengths:
- Weaknesses:

## Competitor 3
- Handle / website:
- Followers & posting frequency:
- Content that performs best:
- Strengths:
- Weaknesses:

## Opportunities for our client
-
`,
  },
  {
    id: 'brand',
    name: 'Brand Guidelines',
    icon: '🎨',
    description: "The client's look, voice and rules for every edit.",
    body: `# Brand Guidelines

## Logo
- Files & where to find them:
- Minimum size / clear space:

## Colors
- Primary:
- Secondary:
- Background:

## Typography
- Headlines:
- Body / captions:

## Voice
- We sound like:
- We never sound like:

## Video style
- Pacing & music:
- Subtitles style:
- Transitions & effects:
- Intro / outro:

## Don'ts
-
`,
  },
];

export const strategyBody = lang === 'ru' ? ru.strategyBody : enStrategyBody;
export const PAGE_TEMPLATES = lang === 'ru' ? ru.PAGE_TEMPLATES : EN_TEMPLATES;
