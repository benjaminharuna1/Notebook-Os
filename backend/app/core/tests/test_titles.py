from app.core.titles import title_case


def test_capitalises_significant_words_only():
    assert (
        title_case("deep learning for crop yield prediction")
        == "Deep Learning for Crop Yield Prediction"
    )
    assert title_case("a survey of quantum machine learning methods") == (
        "A Survey of Quantum Machine Learning Methods"
    )


def test_first_and_last_word_keep_their_capital_even_when_minor():
    assert title_case("the state of the art") == "The State of the Art"
    assert title_case("what the data is in") == "What the Data Is In"


def test_preserves_acronyms_and_digit_bearing_tokens():
    assert title_case("a survey of LLM agents in education") == "A Survey of LLM Agents in Education"
    assert title_case("COVID-19 severity in small samples") == "COVID-19 Severity in Small Samples"


def test_preserves_deliberate_internal_capitals():
    assert title_case("the iPhone effect on app design") == "The iPhone Effect on App Design"


def test_handles_hyphenated_words():
    assert title_case("state-of-the-art methods") == "State-of-the-Art Methods"


def test_repairs_an_all_caps_title():
    assert (
        title_case("DEEP LEARNING FOR CROP YIELD PREDICTION")
        == "Deep Learning for Crop Yield Prediction"
    )
    assert title_case("A STUDY OF FARMING") == "A Study of Farming"


def test_repairs_an_all_caps_title_but_keeps_named_acronyms():
    assert (
        title_case("ARTIFICIAL INTELLIGENCE AND AI IN HEALTHCARE")
        == "Artificial Intelligence and AI in Healthcare"
    )
    assert title_case("USING NLP FOR TEXT MINING") == "Using NLP for Text Mining"


def test_leaves_a_pure_acronym_phrase_alone():
    # No word is long enough to prove this was written as prose, so guessing
    # would be more likely to mangle it than to help.
    assert title_case("AI IN ML") == "AI IN ML"


def test_handles_empty_and_none():
    assert title_case("") == ""
    assert title_case(None) is None
