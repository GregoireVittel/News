const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { normalizeFeedItems, partitionFinancialArticles } = require('../feed-utils.js');

const feed = {name:'Google News — BNP Paribas (EN)', language:'en', category:'Financial markets and economics', subgroup:'BNP Paribas', aggregator:true};

test('Google News BNP stories retain the publisher instead of counting Google as publisher', () => {
  const [article] = normalizeFeedItems([{title:'TEST ONLY BNP Paribas buyback - Test Publisher', link:'https://news.google.com/rss/articles/test', source:'Test Publisher'}], feed);
  assert.equal(article.sourceName, 'Test Publisher');
  assert.equal(article.category, 'Financial');
  assert.equal(article.subgroup, 'BNP Paribas');
  assert.equal(article.language, 'en');
  assert.equal(article.link, 'https://news.google.com/rss/articles/test');
  const [converted] = normalizeFeedItems([{title:'TEST ONLY BNP Paribas dividends - Test Publisher'}], feed);
  assert.equal(converted.sourceName, 'Test Publisher');
});

test('BNP feeds reject unrelated and tournament-only stories without losing bank or stock headlines', () => {
  const items = [
    {title:'TEST ONLY Other bank earnings - Test Publisher'},
    {title:'TEST ONLY BNP Paribas Open: tennis final - Test Publisher'},
    {title:'TEST ONLY BNP Paribas bank announces sponsorship investment - Test Publisher'},
    {title:'TEST ONLY BNP Paribas stock buyback - Test Publisher'},
  ];
  assert.deepEqual(normalizeFeedItems(items, feed).map(a=>a.title), items.slice(2).map(a=>a.title));
});

test('ordinary publishers keep their identity and BNP subjects join Financial despite geographic feed', () => {
  const [article] = normalizeFeedItems([{title:'TEST ONLY BNP Paribas bank grows in Poland', source:'Ignored external value'}], {name:'Test Publisher', language:'pl', category:'Poland'});
  assert.equal(article.sourceName, 'Test Publisher');
  assert.equal(article.category, 'Financial');
  assert.equal(article.subgroup, 'BNP Paribas');
});

test('financial partition includes every BNP story once, even the first/top story', () => {
  const articles = [
    {link:'bnp-top', category:'Financial', subgroup:'BNP Paribas'},
    {link:'world', category:'World'},
    {link:'markets', category:'Financial'},
    {link:'bnp-later', category:'Financial', subgroup:'BNP Paribas'},
  ];
  const {general, financial, bnp} = partitionFinancialArticles(articles);
  assert.deepEqual(general, [articles[1]]);
  assert.deepEqual(financial, [articles[2]]);
  assert.deepEqual(bnp, [articles[0],articles[3]]);
  assert.equal(new Set([...general,...financial,...bnp].map(a=>a.link)).size, articles.length);
});

test('Google News uses full XML first rather than the unordered ten-item rss2json subset', async () => {
  const calls = [];
  const item = {title:'TEST ONLY BNP Paribas bank buyback - Test Publisher'};
  const context = {AbortSignal, console, normalizeFeedItems, categoryForFeed:f=>f.category,
    parseXmlFeed:xml=>{ assert.equal(xml,'TEST ONLY XML');return [item]; },
    fetch:async url=>{ calls.push(url);return {ok:true,text:async()=>'TEST ONLY XML',json:async()=>({status:'ok',items:[]})}; }};
  vm.createContext(context);
  const live = fs.readFileSync(require('node:path').join(__dirname, '../live.html'), 'utf8');
  const code = 'const fetchFeed = ' + live.split('const fetchFeed = ')[1].split('// --- COMPONENTS ---')[0];
  vm.runInContext(code + '\nglobalThis.run = fetchFeed;', context);
  const result = await context.run({...feed,url:'https://news.google.com/rss/search?q=test'});
  assert.equal(result.items.length,1);
  assert.equal(calls.length,1);
  assert.ok(calls[0].startsWith('https://api.allorigins.win/raw?'));
});

test('Google XML failure retains available JSON stories and explicitly flags limited results', async () => {
  const calls = [];
  const context = {AbortSignal, console, normalizeFeedItems, categoryForFeed:f=>f.category,
    parseXmlFeed:()=>{throw new Error('Unexpected XML parsing');},
    fetch:async url=>{ calls.push(url); if(url.includes('allorigins'))throw new Error('TEST ONLY outage');
      return {ok:true,json:async()=>({status:'ok',items:[{title:'TEST ONLY BNP Paribas earnings - Test Publisher'}]})}; }};
  vm.createContext(context);
  const live = fs.readFileSync(require('node:path').join(__dirname, '../live.html'), 'utf8');
  const code = 'const fetchFeed = ' + live.split('const fetchFeed = ')[1].split('// --- COMPONENTS ---')[0];
  vm.runInContext(code + '\nglobalThis.run = fetchFeed;', context);
  const result = await context.run({...feed,url:'https://news.google.com/rss/search?q=test'});
  assert.equal(result.items.length,1);
  assert.equal(result.failed,false);
  assert.equal(result.limited,true);
  assert.equal(calls.length,2);
});
