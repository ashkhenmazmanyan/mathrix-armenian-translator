# Translation comparison (float16, beams 4)

| Model | Load (s) | Peak GPU memory (MB) | Mean time / sentence (s) | Worst (s) |
|---|---|---|---|---|
| opus-mt | 3.9 | 165 | 0.10 | 0.17 |
| nllb-600M | 6.7 | 1220 | 0.24 | 0.36 |
| nllb-1.3B | 14.6 | 2678 | 0.42 | 0.59 |

Score each ASR translation: 2 = meaning correct, 1 = gist understandable, 0 = wrong or misleading.

**Draft scores on ASR input (max 22):** opus-mt 7, nllb-600M 10, nllb-1.3B 12

## me_01

**HY (REF):** Բարև, ինչպե՞ս ես։ Վաղուց չէինք խոսել։ Ի՞նչ նորություն կա, ո՞նց են գործերդ։

- opus-mt: Hi, how are you? We didn't speak tomorrow. What news are you doing?
- nllb-600M: Hi, how are you? We haven't spoken in a long time. What's the news? What are you doing?
- nllb-1.3B: Hi, how are you? It's been a while. What's up?

**HY (ASR, large-v3):** Բարև, ինչպես ես, վաղուծ չենք խոսել, ինչ նորություն կա, բոնց են գործերը։

- opus-mt (0.07s): Hi, as I'm not talking early on, what news is there, it's kind of hot stuff.  
  score: 1  ('what news is there' ok; rest wrong)
- nllb-600M (0.19s): Well, like me, we don't talk about what's new, what's going on.  
  score: 1  ('we don't talk' misleading, 'what's new' ok)
- nllb-1.3B (0.32s): Hey, like me, we haven't talked about what's new, that's business.  
  score: 1  ('haven't talked', 'what's new' ok; rest odd)

## me_02

**HY (REF):** Այսօր նոյեմբերի մեկն է, երկու հազար քսանվեց թվականը։ Տոմսն արժե տասներկու հազար հինգ հարյուր դրամ։

- opus-mt: It's just one, two thousand years. It's worth 12 thousand dollars.
- nllb-600M: Today is November 1, the year two thousand twenty-six. The ticket costs twelve thousand five hundred drachmas.
- nllb-1.3B: Today is November 1, the year two thousand twenty-six. The ticket costs twelve thousand five hundred drachmas.

**HY (ASR, large-v3):** Այսօր նոյեմբերի մեկն է, 2026 թվական է, տոմս նարժ է 12,500 զրամ։

+

- opus-mt (0.06s): It's one day, 2026, he's a ticket on 12,500.  
  score: 1  (year/number ok, date and 'ticket costs' lost)
- nllb-600M (0.15s): It's November 1, 2026, and the price is 12,500.  
  score: 2  (date, year, price all right)
- nllb-1.3B (0.27s): It's November 1st, 2026, and the fare is 12,500.  
  score: 2  (date, year, fare all right)

## me_03

**HY (REF):** Երեկ Աննայի ու Դավիթի հետ գնացինք Երևան։ Քայլեցինք Հյուսիսային պողոտայով և հասանք Կասկադ։ Այնուհետև՝ սրճեցինք։

- opus-mt: Then we went with Anna and David.
- nllb-600M: Yesterday we went to Yerevan with Hannah and David. We walked along the northern highway and came to Khaskad.
- nllb-1.3B: Yesterday we went to Yerevan with Anna and David. We walked down North Avenue and reached the Cascades.

**HY (ASR, large-v3):** Երեք աննայի ու դավիթի հետ գնացինք երևան, կայլեցինք հյուսային բողոտայով և հասանք կասկատ, այն ու հետև սրջեցինք։

- opus-mt (0.11s): So we went with three of them and I went with them, and we went with them, and we went there with them, and we went with them.  
  score: 0  (repetitive nonsense)
- nllb-600M (0.33s): Three of us, together with Anna and David, went to the plain, and we stopped on the north side of the highway, and we came to Saskatchewan, and we turned around.  
  score: 0  ('three of us', 'plain', 'Saskatchewan': misleading)
- nllb-1.3B (0.42s): Three of us, Anna and David, went to Yerevan, followed the northern road and reached the cascade, which we turned back.  
  score: 1  (Anna, David, Yerevan, cascade ok; 'three of us' from ASR error)

## me_04

**HY (REF):** Ես վերջերս ավարտել եմ համալսարանը և հիմա փնտրում եմ աշխատանք, որտեղ կկարողանամ կիրառել մաթեմատիկայի գիտելիքներս ու սովորել նոր բաներ։

- opus-mt: I've just finished university recently, and I'm looking for work where I can apply mathematics and learn new things.
- nllb-600M: I just graduated from university and now I'm looking for a job where I can apply my knowledge of mathematics and learn new things.
- nllb-1.3B: I recently graduated from college and am now looking for a job where I can apply my math skills and learn new things.

**HY (ASR, large-v3):** Ես վերջերը սավարտել եմ համալ սրանը և հիմա պնտրում եմ աշխատանք, որտեղ կկարող անեմ գիրարել մաթեմաթիկայի գիտերիքներս ու սովորել նոր բաներ։

- opus-mt (0.12s): I'm going to end this thing, and now I'm going to do a job where I'm going to get a fast-being, and I'm going to learn new things.  
  score: 0  ('end this thing', 'fast-being')
- nllb-600M (0.23s): I graduated with a degree in math and now I'm looking for a job where I can get my math skills up and learn new things.  
  score: 1  (job/math/learn ok; 'degree in math' wrong)
- nllb-1.3B (0.41s): I'm finally done with this, and now I'm looking for a job where I can broaden my math skills and learn new things.  
  score: 1  (job/math/learn ok; 'finally done with this' vague)

## me_05

**HY (REF):** Գիտե՞ս ինչ, այսօր այնքան զբաղված էի, որ նույնիսկ չհասցրի ճաշել։ Մտածում էի՝ շուտ կավարտեմ, բայց լրիվ ուրիշ բան ստացվեց։

- opus-mt: You know, I was so busy today that I didn't even have a meal.
- nllb-600M: You know, I was so busy today that I didn't even get to eat. I thought I'd finish soon, but I got something else.
- nllb-1.3B: You know, I was so busy today, I didn't even get to eat.

**HY (ASR, large-v3):** Կիտես ինչ, այսօր այնքան զբաղված էի, որ նույն իսկ չհաստրի ճաշել, մտացում էի շուտ կավարտեմ, բայց լերիվ ուրիշպան ստացվեց։

- opus-mt (0.11s): What I was so busy today is that I didn't have a meal, I'm going to finish quickly, but I'm going to have another car.  
  score: 1  (busy, no meal ok; 'another car')
- nllb-600M (0.27s): You see, I was so busy today that I couldn't eat the same meal, and I thought I was going to finish soon, but I got a full lunch.  
  score: 1  (busy, couldn't eat ok; ending wrong)
- nllb-1.3B (0.57s): You know, I've been so busy today, I didn't even sit down to eat, and I thought I'd be done early, but I've got a full plate.  
  score: 2  (meaning kept incl. ending ('full plate'))

## video_01

**HY (REF):** Եթե խոսենք ավելի շատ էսպես հարաբերությունների և մեր հաղորդման հետ կապված, այ, ի՞նչ ակնկալիքներ ունեք էսօրվա թողարկումից, որովհետև  ամեն դեպ

- opus-mt: If we talk more about relationships and our sharing, what do you expect from the cover, because by the way, you're talking about each other?
- nllb-600M: If we talk more about relationships and our communication, well, what do you expect from today's release, because anyway?
- nllb-1.3B: Speaking more about relationships and our show, yeah, what are your expectations for tonight's show, because anyway,

**HY (ASR, large-v3):** Եթե խոսենք ավելի շատ ասպես հարաբերությունների և մեջ հաղորդման հետ կապված է, ինչ ակնկալիքներ ունեք է սրվա թողարկում ինձ, որովհետև ամեն դեպ։

- opus-mt (0.10s): If you talk more about relationships and arguments, what you expect about me is because, by the way, it's about how you're going to deal with me.  
  score: 1  (relationships/expectations; 'deal with me' wrong)
- nllb-600M (0.21s): If we're talking more about relationships and communication, what you're expecting is what makes me nervous, because anyway.  
  score: 1  (relationships/expecting ok; 'makes me nervous' wrong)
- nllb-1.3B (0.40s): If we talk more like relationships and in terms of communication, what expectations do you have of a sharp release from me, because anyway.  
  score: 1  (expectations ok; 'sharp release from me' wrong)

## video_02

**HY (REF):** Իհարկե, քանի որ ես չունեմ ընտրյալ, իհարկե շատ հաճելի կլինի եթե գտնեմ նրան այս հաղորդման շնորհիվ։ Ու կախված արդեն շփու

- opus-mt: Of course, because I don't have a chosen name, it's really good to find him through this break, and T.
- nllb-600M: Of course, since I don't have a choice, it would certainly be great if I could find him through this transmission.
- nllb-1.3B: Of course, since I don't have a choice, of course it would be nice if I could find him through this show.

**HY (ASR, large-v3):** Վիարկ է, կանի որ ես չունեմ ընտրյալ, Վիարկ է շատ հաջելի կլինի, եթե կտնեմ նրանայի սավորդմաշնորի, ու կախված արդեն շպում։

- opus-mt (0.13s): I'm sorry I don't have a chosen one, I'm sorry if I'm going to make her look like this, and it doesn't matter how much I'm going to do.  
  score: 1  ('don't have a chosen one' right; rest wrong)
- nllb-600M (0.34s): It's a shame I don't have a choice, it's a shame it'll be a lot of fun if I get into her spongebox, and I'm already hanging by a thread.  
  score: 0  ('spongebox', 'hanging by a thread')
- nllb-1.3B (0.49s): No, because I don't have a choice, no, it would be very convenient if I put her in a green shirt, and she's already hanging.  
  score: 0  ('green shirt': misleading)

## video_03

**HY (REF):** ՀատվածըըըըԷմմա Վոթսոն, ավելի սոցիալական ինչ֊որ բաներ, բայց հետո ինչ֊որ սկսեցիք կարծրատիպային բաներ ասել, մի քիչ, կարծրատիպային ինչ֊որ բաներ

- opus-mt: And then what I started to say was a little bit like,
- nllb-600M: It's Emma Watson, something more social, but then you start saying something stereotypical, a little, something stereotypical.
- nllb-1.3B: Specifically Emma Watson, more social stuff, but then you started saying some stereotypical stuff, a little bit of stereotypical stuff.

**HY (ASR, large-v3):** Հատվածը եմ ոտ սոն, ավելի սոցիալական ինչ-որ բաներ, բայց հետո ինչ-որ սկզեցի կարծրատիպային բաներ ասել, մի գիչ կարծրատիպային ինչ-որ բաներ.

- opus-mt (0.08s): So I'm a bit more social stuff, but then I would say something very hard to say, something like this.  
  score: 0  (vague, no stereotypes)
- nllb-600M (0.23s): I'm addicted to some more social stuff, but then I start saying some stereotypical stuff, a little bit of stereotypical stuff.  
  score: 1  (stereotypical stuff ok; 'addicted', 'I start')
- nllb-1.3B (0.41s): I was hooked on more social stuff, but then I started saying some stereotypical stuff, some very stereotypical stuff.  
  score: 1  (stereotypical stuff ok; 'hooked', 'I started')

## video_04

**HY (REF):** Հասկանամ դուք սենց եք մտածում, որ սերը անկախ ամեն բանից, լավ ու վատ հարաբերություններից կամ դիմացինից, միևնույն ա մարում ա

- opus-mt: I'm sorry you think, love is no matter how good and bad you're, or what you're doing.
- nllb-600M: I understand you're thinking that love, no matter what, good or bad, relationships or the other person, always ends.
- nllb-1.3B: I know you're thinking that no matter what happens, whether it's good or bad, whether it's a relationship or the other person, love just keeps going.

**HY (ASR, large-v3):** Հասկանամ դուք սենցեք մտածում, որ սերը անկախ ամենբանից լավու վատ հարաբերություններից կամ դիմացինից միրեվ նույնամ մարում է։

- opus-mt (0.10s): I'm going to tell you that love, regardless of the bad relationship in every other person or the other person, gets the same point.  
  score: 1  (love regardless of relationships; ending wrong)
- nllb-600M (0.19s): I understand that you may think that love is the same regardless of good or bad relationships or good or bad relationships.  
  score: 1  (same; misses 'love fades')
- nllb-1.3B (0.44s): Now, I know you're thinking that no matter how bad the relationship, whether it's the best or the worst, love will always be the same.  
  score: 1  (same; says love 'stays the same', opposite of 'fades')

## video_05

**HY (REF):** Բայց էն մակարդակով որ փորում թիթեռնիկներ լինեն, այդպիսի սիրահարվածություն ե՞րբ եք ունեցել։   Ըմ, չեմ ունեցել, որ էդ թիթեռնիկները որ հասնեն փորի

- opus-mt: But the level is that you've got this kind of love in love. I don't have to know, because I don't have to know that the bacteria are going to get out of the belly.
- nllb-600M: But to the extent that there are butterflies digging, when have you ever been in love like this?
- nllb-1.3B: But at the level of butterflies in a burrow, when did you have that kind of infatuation?

**HY (ASR, large-v3):** Պայց այն մակարդակով, որ փորում թիթերնիքներ լինեն, այդպիսի սիրահարվածություն երբ եք ունեցել։ Չեմ ունեցել էր, թիթերնիքները, որ հասնեն փորում։

- opus-mt (0.12s): From the level that you've got to be in, you've had this kind of passion. I haven't had a car, you've had a car to jump.  
  score: 0  ('car to jump')
- nllb-600M (0.22s): But to the extent that there are butterflies in the excavation, that's the kind of love you've ever had.  
  score: 1  (butterflies + love kept; question lost)
- nllb-1.3B (0.40s): But at a level where there are butterflies in the pit, that's the kind of love you've ever had.  
  score: 1  (butterflies + love kept; question lost)

## video_06

**HY (REF):** Քսանհինգ տարեկան, ես մասնագիտությամբ մենեջեր եմ։ Աշխատում եմ հյուրանոցային֊ռեսորանոցային համալիրում։ Այժմ էլ երրորդ մասնագիտությամբ իրավաբան ապագա, այժմ սովորում եմ։

- opus-mt: I'm a professional manager. I'm working in a hotel station, and now I'm a third-year-old lawyer, I'm learning now.
- nllb-600M: Twenty-five years old, I'm a manager by profession. I work in a hotel-resort complex. Now I'm a lawyer by profession.
- nllb-1.3B: I'm 25 years old, I'm a manager by profession, I work in a hotel-restaurant complex, and now I'm a lawyer by profession, now I'm studying.

**HY (ASR, large-v3):** 25 տարեկան, ես մասակտության մենեջեր եմ, աշխատում եմ միլորնությային համալիրում, այժրում էլ երորդ մասակտության պիրավաբան ապագա, այժրում սովորում եմ։

- opus-mt (0.17s): I'm 25 years old, I'm a part-year-old manager, I'm working in the N-Aveny Valley, and I'm going to be a part of the 21st century, and I'm learning a little bit.  
  score: 1  (25, manager, learning ok; rest garbled)
- nllb-600M (0.34s): I'm 25 years old, I'm a math manager, I work in a multi-millionaire complex, and I'm a math psychologist in the future, and I'm a math student.  
  score: 1  (25, manager, student ok; 'math psychologist')
- nllb-1.3B (0.59s): I'm 25 years old, I'm a crowdfunding manager, I work in a crowdfunding complex, I'm a future crowdfunder, I'm a student.  
  score: 1  (25, manager, student ok; 'crowdfunding' x3)

## Conclusions

| Model | Score on ASR input (max 22) | Peak GPU memory | Mean / worst time per sentence |
|---|---|---|---|
| opus-mt | 7 | 165 MB | 0.10 / 0.17 s |
| nllb-600M | 10 | 1220 MB | 0.24 / 0.36 s |
| nllb-1.3B | 12 | 2678 MB | 0.42 / 0.59 s |

- Pre-set rule: exclude > ~3 GB or > 1 s per sentence (none excluded); pick the highest score; if within ~2 points, pick the smaller/faster one.
- nllb-1.3B leads nllb-600M by 2 points -> within the margin -> **nllb-600M** (1.3B kept as an option).
- Memory also favours 600M: large-v3 int8 (~2.0 GB) + 1.3B (~2.7 GB) + desktop (~0.6 GB) leaves almost nothing for the speaker model or a video call.
- opus-mt is fast but poor even on clean text (e.g. 'two thousand years', '12 thousand dollars').
- **The bottleneck is speech recognition, not translation:** NLLB's translations of the clean REF text are mostly correct,
  while the same models on the ASR text drop to ~1/2 per clip. ASR errors such as Երեկ->Երեք ('yesterday'->'three') pass straight through.
- Idiom/ambiguity: 'փորում' (in the stomach / digging) was translated as 'digging'/'pit' by every model, even on clean text.
