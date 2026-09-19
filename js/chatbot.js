/**
 * Maharashtra Skill Intelligence — Grounded Chatbot Engine (JS Port)
 *
 * Architecture mirrors engines/chatbot/chatbot_engine.py:
 *   1. Load and parse MSSDS CSV dataset (same data the Python engine uses)
 *   2. Extract entities: district, sector from user query
 *   3. Build a precise, structured evidence block from the real dataset
 *   4. Send [question + evidence] to Groq -> natural, precise answer
 *   5. For non-data general questions -> Groq answers from its own knowledge
 *
 * Groq system prompt allows BOTH dataset-grounded AND general answers.
 */

(function (global) {
  'use strict';

  /* ── Dataset CSV path (relative to server root) ── */
  var CSV_PATH = 'data/mssds_district_sector_intelligence.csv';

  /* ── Groq configuration ── */
  var GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions';

  /* ── State ── */
  var _dataset = [];
  var _districts = [];
  var _sectors = [];
  var _dataLoaded = false;
  var _dataLoading = false;
  var _loadCallbacks = [];

  /* ── Conversation context (mirrors Python context dict) ── */
  var _context = {
    district: null,
    sector: null,
    last_result: null
  };

  /* =========================================================
     CSV PARSER — lightweight, no dependencies
     ========================================================= */
  function parseCSV(text) {
    var lines = text.split(/\r?\n/);
    if (!lines.length) return [];
    var headers = lines[0].split(',').map(function (h) { return h.trim(); });
    var rows = [];
    for (var i = 1; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) continue;
      var vals = line.split(',');
      var obj = {};
      for (var j = 0; j < headers.length; j++) {
        obj[headers[j]] = (vals[j] || '').trim();
      }
      rows.push(obj);
    }
    return rows;
  }

  /* =========================================================
     DATASET LOADING
     ========================================================= */
  function loadDataset(callback) {
    if (_dataLoaded) { callback(null); return; }
    if (_dataLoading) { _loadCallbacks.push(callback); return; }
    _dataLoading = true;
    _loadCallbacks.push(callback);

    fetch(CSV_PATH)
      .then(function (res) {
        if (!res.ok) throw new Error('CSV HTTP ' + res.status);
        return res.text();
      })
      .then(function (text) {
        _dataset = parseCSV(text);
        var distSet = {}, secSet = {};
        _dataset.forEach(function (r) {
          if (r.district) distSet[r.district] = true;
          if (r.sector) secSet[r.sector] = true;
        });
        _districts = Object.keys(distSet).sort(function (a, b) { return b.length - a.length; });
        _sectors = Object.keys(secSet).sort(function (a, b) { return b.length - a.length; });
        _dataLoaded = true;
        _dataLoading = false;
        console.log('[SIH Chatbot] Dataset loaded:', _dataset.length, 'rows,', _districts.length, 'districts,', _sectors.length, 'sectors');
        _loadCallbacks.forEach(function (cb) { cb(null); });
        _loadCallbacks = [];
      })
      .catch(function (err) {
        _dataLoading = false;
        console.warn('[SIH Chatbot] Dataset load failed — using fallback:', err.message);
        _loadCallbacks.forEach(function (cb) { cb(err); });
        _loadCallbacks = [];
      });
  }

  /* =========================================================
     ENTITY EXTRACTION (mirrors chatbot_engine.py extract_entities)
     ========================================================= */
  function escapeRx(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  function extractEntities(text) {
    var lower = text.toLowerCase();
    var matchedDistrict = null, matchedSector = null;
    var dList = _dataLoaded ? _districts : FALLBACK_DISTRICTS_LIST;
    var sList = _dataLoaded ? _sectors : FALLBACK_SECTORS_LIST;

    for (var d = 0; d < dList.length; d++) {
      if (new RegExp('\\b' + escapeRx(dList[d].toLowerCase()) + '\\b').test(lower)) {
        matchedDistrict = dList[d]; break;
      }
    }
    if (!matchedDistrict && /\bnasik\b/.test(lower)) matchedDistrict = 'Nashik';

    for (var s = 0; s < sList.length; s++) {
      if (new RegExp('\\b' + escapeRx(sList[s].toLowerCase()) + '\\b').test(lower)) {
        matchedSector = sList[s]; break;
      }
    }
    if (!matchedSector && /\b(?:it|information technology)\s+(?:jobs?|careers?|sector|skills?|work)\b/.test(lower)) {
      matchedSector = 'IT/ITeS';
    }
    return { district: matchedDistrict, sector: matchedSector };
  }

  /* =========================================================
     DATASET QUERY HELPERS
     ========================================================= */
  function getDemandBand(val) {
    if (val >= 300) return 'High';
    if (val >= 100) return 'Moderate';
    return 'Low';
  }

  function getDistrictData(district) {
    return _dataset.filter(function (r) {
      return r.district && r.district.toLowerCase() === district.toLowerCase();
    });
  }

  function getDistrictSectorRow(district, sector) {
    var rows = _dataset.filter(function (r) {
      return r.district && r.district.toLowerCase() === district.toLowerCase()
          && r.sector && r.sector.toLowerCase() === sector.toLowerCase();
    });
    return rows[0] || null;
  }

  function getProjectedSectors(district) {
    return getDistrictData(district)
      .filter(function (r) { return (r.projection_available || '').toLowerCase() === 'true'; })
      .map(function (r) {
        var pt = parseFloat(r.projected_training) || 0;
        return {
          sector: r.sector,
          projected_training: pt,
          evidence_confidence: parseFloat(r.evidence_confidence) || 0,
          demand_band: getDemandBand(pt),
          industry_size: r.industry_size,
          candidate_aspiration: r.candidate_aspiration
        };
      })
      .sort(function (a, b) { return b.projected_training - a.projected_training; });
  }

  /* =========================================================
     EVIDENCE BUILDER — key function, mirrors Python evidence_context
     Produces structured text that Groq uses as ground truth
     ========================================================= */
  function buildEvidence(question, district, sector) {
    var qLower = question.toLowerCase();
    var SKILL_KEYWORDS = /\b(iti|mssds|dvet|skill|trade|training|demand|intake|sector|maharashtra|district|projected|vocational|workforce|industry|employment)\b/;

    // No entities and not a skill question => general question
    if (!district && !sector && !SKILL_KEYWORDS.test(qLower)) {
      return { evidence: '', intent: 'general' };
    }

    // Statewide overview (no specific district/sector)
    if (!district && !sector && SKILL_KEYWORDS.test(qLower)) {
      var stateSectors = {};
      _dataset.forEach(function (r) {
        if ((r.projection_available || '').toLowerCase() === 'true' && r.projected_training) {
          stateSectors[r.sector] = (stateSectors[r.sector] || 0) + (parseFloat(r.projected_training) || 0);
        }
      });
      var topState = Object.keys(stateSectors)
        .sort(function (a, b) { return stateSectors[b] - stateSectors[a]; })
        .slice(0, 6)
        .map(function (s) { return s + ': ~' + Math.round(stateSectors[s]) + ' trainees'; })
        .join('\n');
      return {
        evidence: 'Maharashtra Statewide Skill Data (MSSDS 2022-23 Official Records)\n'
          + 'Top Sectors by Projected Training Demand across all 36 districts:\n' + topState
          + '\nSource: MSSDS/DVET/DGT official records.',
        intent: 'statewide'
      };
    }

    // District + Sector: precise lookup
    if (district && sector) {
      var row = getDistrictSectorRow(district, sector);
      if (!row) {
        var available = getProjectedSectors(district).map(function (s) { return s.sector; }).join(', ');
        return {
          evidence: 'No data found for sector "' + sector + '" in ' + district + '.\n'
            + 'Sectors with projection data for ' + district + ': ' + (available || 'none found'),
          intent: 'sector_not_found'
        };
      }
      var pt = parseFloat(row.projected_training) || null;
      var conf = parseFloat(row.evidence_confidence) || null;
      var projAvail = (row.projection_available || '').toLowerCase() === 'true';
      var band = pt !== null ? getDemandBand(pt) : 'Unknown';

      var lines = [
        'District: ' + district,
        'Sector: ' + sector,
        'Projection Available: ' + (projAvail ? 'Yes' : 'No')
      ];
      if (pt !== null) lines.push('Projected Training Demand: ~' + Math.round(pt) + ' trainees');
      if (pt !== null) lines.push('Demand Band: ' + band);
      if (conf !== null) lines.push('Evidence Confidence / Data Coverage: ' + Math.round(conf * 100) + '%');
      if (row.industry_size) lines.push('Industry Size Indicator: ' + row.industry_size);
      if (row.candidate_aspiration) lines.push('Candidate Aspiration Count: ' + row.candidate_aspiration);
      if (row.mssds_trained_2022_23) lines.push('MSSDS Trained (2022-23): ' + row.mssds_trained_2022_23);
      if (row.dsdp_training) lines.push('DSDP Training Records: ' + row.dsdp_training);
      if (row.organization_count) lines.push('Organization Count: ' + row.organization_count);
      lines.push('Source: Official MSSDS/DVET/DGT records.');

      return { evidence: lines.join('\n'), intent: 'district_sector' };
    }

    // District overview (no sector)
    if (district && !sector) {
      var projected = getProjectedSectors(district);
      var allRows = getDistrictData(district);
      if (!allRows.length) {
        return { evidence: 'No records found for district: ' + district, intent: 'district_not_found' };
      }

      var totalDemand = projected.reduce(function (a, s) { return a + s.projected_training; }, 0);
      var secLines = projected.map(function (s, i) {
        return (i + 1) + '. ' + s.sector + ': ~' + Math.round(s.projected_training) + ' trainees'
          + ' (' + s.demand_band + ' Demand, ' + Math.round(s.evidence_confidence * 100) + '% confidence)';
      }).join('\n');

      var nonProjected = allRows
        .filter(function (r) { return (r.projection_available || '').toLowerCase() !== 'true'; })
        .map(function (r) { return r.sector; }).slice(0, 8);

      var evLines = [
        'District: ' + district,
        'Data Source: MSSDS 2022-23 Official Records',
        '',
        'Sectors with ML Projected Training Demand:',
        secLines || 'None available for this district',
        '',
        'Total Projected Training Demand: ~' + Math.round(totalDemand) + ' trainees'
      ];
      if (nonProjected.length) {
        evLines.push('Other tracked sectors (no projection model yet): ' + nonProjected.join(', '));
      }
      evLines.push('');
      evLines.push('Note: Figures are ML-projected from MSSDS/DVET econometric model trained on historical data.');

      return { evidence: evLines.join('\n'), intent: 'district_overview' };
    }

    // Sector across all districts (no specific district)
    if (!district && sector) {
      var sectorRows = _dataset.filter(function (r) {
        return r.sector && r.sector.toLowerCase() === sector.toLowerCase()
          && (r.projection_available || '').toLowerCase() === 'true' && r.projected_training;
      });
      if (!sectorRows.length) {
        return { evidence: 'No projected training data for sector: ' + sector + ' in Maharashtra.', intent: 'sector_notfound' };
      }
      var stateTotal = sectorRows.reduce(function (a, r) { return a + (parseFloat(r.projected_training) || 0); }, 0);
      var topDists = sectorRows.slice()
        .sort(function (a, b) { return (parseFloat(b.projected_training) || 0) - (parseFloat(a.projected_training) || 0); })
        .slice(0, 6)
        .map(function (r) { return r.district + ': ~' + Math.round(parseFloat(r.projected_training)) + ' trainees'; })
        .join('\n');
      return {
        evidence: 'Sector: ' + sector + ' (Statewide Maharashtra)\n'
          + 'Total Projected Training Demand: ~' + Math.round(stateTotal) + ' trainees across ' + sectorRows.length + ' districts\n'
          + 'Top Districts:\n' + topDists + '\nSource: MSSDS 2022-23 Official Records.',
        intent: 'sector_statewide'
      };
    }

    return { evidence: '', intent: 'general' };
  }

  /* =========================================================
     GROQ CALL — grounded evidence + general knowledge in one prompt
     ========================================================= */
  var GROQ_SYSTEM_PROMPT = [
    'You are the Maharashtra Skill Intelligence Assistant — an intelligent AI advisor for Maharashtra skill development and workforce planning.',
    '',
    'CRITICAL INSTRUCTION ON HOW TO TALK ABOUT DATA & RECORDS:',
    '- NEVER say "the dataset you shared", "the provided dataset", "in the dataset provided", "the records you gave me", or similar phrases.',
    '- The user did NOT provide any data or dataset to you. You are the system that inherently possesses official Maharashtra Skill Development Mission (MSSDS) intelligence and records.',
    '- Refer to records naturally as "Official skill records", "State skill intelligence records", "Maharashtra skill data", or "District records".',
    '  Examples of natural phrasing:',
    '  * "According to official skill records for Pune..."',
    '  * "Official records show projected training demand across sectors..."',
    '  * "State intelligence records indicate..."',
    '',
    'CAPABILITIES & DOMAIN RULES:',
    '1. MAHARASHTRA SKILL INTELLIGENCE (Districts, sectors, workforce demand, ITI training):',
    '   - Use the verified official records provided below for exact statistics. Never invent numbers.',
    '   - Use "Projected Training Demand" (not "shortage").',
    '   - If the user asks for a metric not present in the records (such as ITI trade intake capacity when only projected demand is recorded), explain naturally: "Official skill intelligence records currently track projected training demand for this district rather than ITI intake capacity."',
    '',
    '2. GENERAL QUESTIONS (Science, technology, mathematics, history, geography, coding, etc.):',
    '   - Answer freely, helpfully, and accurately from your general knowledge.',
    '   - Never say "I can only answer skill questions" when answering general questions.',
    '',
    'RULES:',
    '- Be precise, natural, and conversational. Not robotic.',
    '- Use bullet points or numbered lists when listing multiple items.',
    '- If a question has both data and general parts, address both.',
    '- Keep answers concise and well-structured.'
  ].join('\n');

  function callGroq(question, evidenceText, groqKey, groqModel) {
    var userContent = 'User question: ' + question;
    if (evidenceText) {
      userContent += '\n\n=== OFFICIAL MAHARASHTRA SKILL INTELLIGENCE RECORDS ===\n'
        + evidenceText
        + '\n=== END OF OFFICIAL RECORDS ===\n\nInstructions: Answer the user\'s question naturally. Use the official records above for Maharashtra skill/workforce figures, and your general knowledge for any other topics. Do NOT say the user provided or shared this data.';
    }

    return fetch(GROQ_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + groqKey
      },
      body: JSON.stringify({
        model: groqModel || 'openai/gpt-oss-120b',
        messages: [
          { role: 'system', content: GROQ_SYSTEM_PROMPT },
          { role: 'user', content: userContent }
        ],
        temperature: 0.45,
        max_tokens: 1200
      })
    })
    .then(function (res) {
      if (!res.ok) return res.text().then(function (t) { throw new Error('Groq ' + res.status + ': ' + t.slice(0, 200)); });
      return res.json();
    })
    .then(function (data) {
      if (data.choices && data.choices[0] && data.choices[0].message) {
        return data.choices[0].message.content.trim();
      }
      throw new Error('No content in Groq response');
    });
  }

  /* =========================================================
     QUICK CONVERSATIONAL RESPONSES (no Groq or dataset needed)
     ========================================================= */
  var GREETINGS = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'good night', 'namaste', 'how are you', 'hlo', 'hii'];
  var CAPABILITIES = ['who are you', 'what can you do', 'help', 'what are your features', 'what r u', 'who r u'];
  var THANKS = ['thanks', 'thank you', 'thx', 'tq', 'thank you so much'];
  var FAREWELLS = ['bye', 'goodbye', 'see you', 'exit', 'quit', 'cya'];

  function checkQuickResponse(query) {
    var q = query.toLowerCase().trim().replace(/[^\w\s]/g, '');
    var i;
    for (i = 0; i < GREETINGS.length; i++) {
      var g = GREETINGS[i];
      if (q === g || q === (g + ' there') || q === (g + ' assistant') || q === (g + ' bot')) {
        return 'Hello! \ud83d\udc4b I\'m the **Maharashtra Skill Intelligence Assistant**.\n\nI can help you with:\n\u2022 **District & Skill Analytics**: Projected training demand, sector analysis, and ITI trade data for all 36 Maharashtra districts\n\u2022 **General questions**: Science, history, math, coding, current events \u2014 anything!\n\nJust ask away!';
      }
    }
    for (i = 0; i < CAPABILITIES.length; i++) {
      if (q.indexOf(CAPABILITIES[i]) !== -1 || q === CAPABILITIES[i]) {
        return 'I am the **Maharashtra Skill Intelligence Assistant** \u2014 powered by Maharashtra State Skill Intelligence & AI.\n\n**I can answer:**\n\u2022 Projected training demand for any district & sector (from official records)\n\u2022 Sector rankings, demand bands, evidence confidence scores\n\u2022 Training-capacity alignment for districts\n\u2022 General knowledge \u2014 science, history, geography, coding, etc.\n\n**Examples:**\n\u2022 *"What is the training demand for Construction in Pune?"*\n\u2022 *"Top sectors in Nashik"*\n\u2022 *"What is machine learning?"*\n\u2022 *"Training demand for Agriculture across Maharashtra"*';
      }
    }
    for (i = 0; i < THANKS.length; i++) {
      if (q === THANKS[i] || q.startsWith(THANKS[i] + ' ')) {
        return 'You\'re welcome! Feel free to ask more about Maharashtra skill data or anything else.';
      }
    }
    for (i = 0; i < FAREWELLS.length; i++) {
      if (q === FAREWELLS[i] || q.startsWith(FAREWELLS[i] + ' ')) {
        return 'Goodbye! Come back anytime for Maharashtra skill intelligence insights.';
      }
    }
    return null;
  }

  /* =========================================================
     FALLBACK STRUCTURED ANSWER (when Groq is unavailable)
     ========================================================= */
  function buildFallbackAnswer(district, sector, ev) {
    if (ev.intent === 'district_sector' && district && sector) {
      var row = getDistrictSectorRow(district, sector);
      if (row && row.projected_training) {
        var pt = parseFloat(row.projected_training);
        var conf = parseFloat(row.evidence_confidence) || 0;
        return 'In **' + district + '**, the projected training requirement for **' + sector + '** is approximately **' + Math.round(pt) + ' trainees** (' + getDemandBand(pt) + ' Demand Band, ' + Math.round(conf * 100) + '% evidence confidence).\n\nSource: Official MSSDS/DVET records.';
      }
    }
    if (ev.intent === 'district_overview' && district) {
      var projected = getProjectedSectors(district);
      if (projected.length) {
        var lines = ['**' + district + ' \u2014 Skill & Training Intelligence**\n'];
        projected.forEach(function (s, i) {
          lines.push((i + 1) + '. **' + s.sector + '**: ~' + Math.round(s.projected_training) + ' trainees (' + s.demand_band + ' Demand)');
        });
        lines.push('\n*Source: MSSDS 2022-23 Official Records*');
        return lines.join('\n');
      }
    }
    return ev.evidence || 'No specific data found. Please ask about a Maharashtra district, sector, or ITI trade.';
  }

  /* =========================================================
     FALLBACK DISTRICT/SECTOR LISTS (when CSV not yet loaded)
     ========================================================= */
  var FALLBACK_DISTRICTS_LIST = [
    'Chhatrapati Sambhajinagar', 'Mumbai Suburban', 'Mumbai City', 'Ahmednagar',
    'Amravati', 'Bhandara', 'Buldhana', 'Chandrapur', 'Dharashiv', 'Gadchiroli',
    'Sindhudurg', 'Nandurbar', 'Akola', 'Beed', 'Dhule', 'Gondia', 'Hingoli',
    'Jalgaon', 'Jalna', 'Kolhapur', 'Latur', 'Nagpur', 'Nanded', 'Nashik',
    'Palghar', 'Parbhani', 'Pune', 'Raigad', 'Ratnagiri', 'Sangli', 'Satara',
    'Solapur', 'Thane', 'Wardha', 'Washim', 'Yavatmal'
  ].sort(function (a, b) { return b.length - a.length; });

  var FALLBACK_SECTORS_LIST = [
    'Food Processing', 'Beauty & Wellness', 'Domestic Workers', 'Capital Goods',
    'Green Jobs', 'Agriculture', 'Automotive', 'Electronics', 'Construction',
    'Healthcare', 'Retail', 'Tourism', 'Textile', 'Apparel', 'Telecom', 'BFSI',
    'IT/ITeS', 'Media', 'Chemical', 'Logistics'
  ].sort(function (a, b) { return b.length - a.length; });

  /* =========================================================
     MAIN PUBLIC FUNCTION: ask(question, options) -> Promise<result>
     ========================================================= */
  function ask(question, options) {
    options = options || {};
    var groqKey = options.groqKey
      || (window.SIH_ENV && window.SIH_ENV.GROQ_API_KEY)
      || (typeof window !== 'undefined' && window.SIH_GROQ_KEY)
      || (typeof localStorage !== 'undefined' ? localStorage.getItem('SIH_GROQ_KEY') : '')
      || '';
    var groqModel = options.groqModel || (window.SIH_ENV && window.SIH_ENV.GROQ_MODEL) || 'openai/gpt-oss-120b';
    var activeDistrict = options.activeDistrict || _context.district || null;

    return new Promise(function (resolve) {

      // Quick responses for pure greetings (no Groq/dataset)
      var quick = checkQuickResponse(question);
      if (quick) {
        var qr = { query: question, status: 'greeting', matched_district: _context.district, matched_sector: _context.sector, answer: quick };
        _context.last_result = qr;
        resolve(qr); return;
      }

      // If question starts with greeting prefix followed by more text, strip prefix so question is answered
      var strippedQuestion = question.replace(/^(?:hello|hi|hey|good\s+(?:morning|afternoon|evening|night)|namaste|hlo|hii)[\s,!.\-]+/i, '').trim();
      if (strippedQuestion) {
        question = strippedQuestion;
      }

      // Load dataset then process
      loadDataset(function () {

        // Entity extraction from query
        var entities = extractEntities(question);

        // Context resolution
        var district = entities.district || activeDistrict || _context.district;
        var sector = entities.sector || (entities.district ? null : _context.sector);

        // Update context
        if (entities.district) { _context.district = entities.district; _context.sector = null; }
        if (sector) _context.sector = sector;

        // Build evidence block
        var ev = _dataLoaded ? buildEvidence(question, district, sector) : { evidence: '', intent: 'general' };

        // Call Groq
        if (groqKey) {
          callGroq(question, ev.evidence, groqKey, groqModel)
            .then(function (answer) {
              var result = {
                query: question, status: 'success',
                matched_district: district, matched_sector: sector,
                answer: answer, intent: ev.intent, evidence_used: !!ev.evidence
              };
              _context.last_result = result;
              resolve(result);
            })
            .catch(function (err) {
              console.warn('[SIH Chatbot] Groq failed:', err.message);
              var fb = ev.evidence ? buildFallbackAnswer(district, sector, ev)
                : 'Unable to reach AI service. Please try again.';
              resolve({ query: question, status: 'fallback', matched_district: district, matched_sector: sector, answer: fb, intent: ev.intent });
            });
        } else {
          var noKey = ev.evidence ? buildFallbackAnswer(district, sector, ev)
            : 'Static mode can answer official Maharashtra district, sector, training-demand, and ITI questions. Select a district and ask about a supported sector or trade.';
          resolve({ query: question, status: 'no_groq', matched_district: district, matched_sector: sector, answer: noKey, intent: ev.intent });
        }
      });
    });
  }

  function resetContext() {
    _context = { district: null, sector: null, last_result: null };
  }

  /* =========================================================
     PUBLIC API
     ========================================================= */
  global.SIHChatbot = {
    ask: ask,
    resetContext: resetContext,
    preloadDataset: function (cb) { loadDataset(cb || function () {}); },
    getContext: function () { return Object.assign({}, _context); },
    getDistricts: function () { return (_dataLoaded ? _districts : FALLBACK_DISTRICTS_LIST).slice(); },
    getSectors: function () { return (_dataLoaded ? _sectors : FALLBACK_SECTORS_LIST).slice(); }
  };

}(typeof window !== 'undefined' ? window : this));
