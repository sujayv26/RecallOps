"""Streamlit frontend for RecallOps - Incident Response AI Agent."""

from datetime import datetime

import streamlit as st

from frontend.api_client import get_api_client

# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="RecallOps - Incident Response AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# Custom CSS
# ============================================================================

st.markdown("""
<style>
    /* Color coding per PRD: Teal=Memory, Amber=Hypothesis, Violet=Verified */
    .memory-badge { background-color: #0d9488; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
    .hypothesis-badge { background-color: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
    .verified-badge { background-color: #8b5cf6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }

    .severity-critical { border-left: 4px solid #ef4444; }
    .severity-high { border-left: 4px solid #f97316; }
    .severity-medium { border-left: 4px solid #eab308; }
    .severity-low { border-left: 4px solid #22c55e; }

    .analysis-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 8px 0; }
    .historical-match { background-color: #f0fdfa; border: 1px solid #0d9488; border-radius: 6px; padding: 12px; margin: 8px 0; }
    .hypothesis-box { background-color: #fffbeb; border: 1px solid #f59e0b; border-radius: 6px; padding: 12px; margin: 8px 0; }
    .verified-box { background-color: #f5f3ff; border: 1px solid #8b5cf6; border-radius: 6px; padding: 12px; margin: 8px 0; }

    .stButton > button[kind="primary"] { background-color: #0d9488; border-color: #0d9488; }
    .stButton > button[kind="primary"]:hover { background-color: #0f766e; border-color: #0f766e; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Session State Initialization
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    if "current_analysis" not in st.session_state:
        st.session_state.current_analysis = None
    if "analysis_history" not in st.session_state:
        st.session_state.analysis_history = []
    if "api_client" not in st.session_state:
        st.session_state.api_client = get_api_client()


init_session_state()

api_client = st.session_state.api_client


# ============================================================================
# Helper Functions
# ============================================================================

def render_severity_badge(severity: str) -> str:
    """Render severity as colored badge."""
    colors = {
        "Critical": ("🔴", "severity-critical"),
        "High": ("🟠", "severity-high"),
        "Medium": ("🟡", "severity-medium"),
        "Low": ("🟢", "severity-low"),
    }
    icon, css_class = colors.get(severity, ("⚪", ""))
    return f'<span class="{css_class}">{icon} {severity}</span>'


def render_confidence_bar(confidence: float) -> str:
    """Render confidence as progress bar."""
    pct = int(confidence * 100)
    color = "#22c55e" if pct >= 80 else "#eab308" if pct >= 60 else "#ef4444"
    return f"""
    <div style="display: flex; align-items: center; gap: 8px;">
        <div style="flex: 1; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden;">
            <div style="width: {pct}%; height: 100%; background: {color};"></div>
        </div>
        <span style="font-size: 0.875rem; font-weight: 500;">{pct}%</span>
    </div>
    """


def render_historical_match(match: dict) -> None:
    """Render a historical memory match."""
    st.markdown(f"""
    <div class="historical-match">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <strong>{match.get('incident_id', 'Unknown')}</strong>
            <span class="memory-badge">📚 MEMORY</span>
        </div>
        <div style="font-size: 0.875rem; color: #374151;">
            <strong>Service:</strong> {match.get('service_name', 'Unknown')}<br>
            <strong>Symptom:</strong> {match.get('symptom', 'N/A')}<br>
            <strong>Verified Root Cause:</strong> {match.get('root_cause', 'N/A')}<br>
            <strong>Verified Resolution:</strong> {match.get('resolution', 'N/A')}
        </div>
        {f"<div style='margin-top: 8px; font-size: 0.75rem; color: #6b7280;'>Similarity: {match.get('similarity_score', 0):.0%}</div>" if match.get('similarity_score') else ""}
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# Sidebar
# ============================================================================

with st.sidebar:
    st.title("🔍 RecallOps")
    st.caption("AI-assisted incident response with persistent memory")

    # Health check
    with st.expander("🔧 System Status", expanded=False):
        if st.button("Check Health"):
            with st.spinner("Checking..."):
                health = api_client.health_check()
                if health.success:
                    st.success("Backend Healthy")
                    deps = health.data.get("dependencies", {})
                    for dep, status_val in deps.items():
                        if dep == "mock_mode":
                            if status_val:
                                st.warning("🧪 Mock Mode: ENABLED (using mock implementations)")
                            else:
                                st.success("🧪 Mock Mode: DISABLED (using real services)")
                        else:
                            icon = "✅" if status_val == "connected" else "⚠️" if status_val == "mock_mode" else "❌"
                            st.write(f"{icon} {dep}: {status_val}")
                else:
                    st.error(f"Backend Unavailable: {health.error}")

    st.divider()

    # Navigation
    page = st.radio(
        "Navigate",
        ["📝 Analyze Incident", "📚 Memory Explorer", "📊 Insights", "📜 History"],
        label_visibility="collapsed"
    )

    st.divider()
    st.caption("v0.1.0 | Hackathon MVP")


# ============================================================================
# Page: Analyze Incident
# ============================================================================

if page == "📝 Analyze Incident":
    st.header("Analyze Incident")
    st.markdown("Submit an incident description to get AI-powered analysis with historical context.")

    # Input Form
    with st.form("incident_form", clear_on_submit=False):
        col1, col2 = st.columns([2, 1])

        with col1:
            service_name = st.text_input(
                "Service Name *",
                placeholder="e.g., Backend API, Payment Service, Auth Service",
                help="Name of the affected service"
            )

            error_description = st.text_area(
                "Error Description *",
                placeholder="Describe the incident: symptoms, error messages, impact...",
                height=120,
                help="What happened? What are the symptoms?"
            )

        with col2:
            log_excerpt = st.text_area(
                "Log Excerpt (optional)",
                placeholder="Paste relevant log lines, stack traces, or metrics...",
                height=200,
                help="Optional: logs help improve analysis accuracy"
            )

        submitted = st.form_submit_button("🔍 Analyze Incident", type="primary", use_container_width=True)

    # Process Submission
    if submitted:
        if not service_name or not error_description:
            st.error("Please fill in Service Name and Error Description")
        else:
            with st.spinner("Recalling team memory and analyzing..."):
                result = api_client.analyze_incident(
                    service_name=service_name,
                    error_description=error_description,
                    log_excerpt=log_excerpt if log_excerpt else None
                )

            if result.success:
                st.session_state.current_analysis = result.data
                st.session_state.analysis_history.insert(0, result.data)
                st.success("Analysis complete!")
                st.rerun()
            else:
                st.error(f"Analysis failed: {result.error}")

    # Display Results
    if st.session_state.current_analysis:
        analysis = st.session_state.current_analysis
        incident_id = analysis.get("incident_id", "unknown")

        st.divider()
        st.subheader("Analysis Results")

        # Severity & Confidence Row
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.markdown(f"**Severity:** {render_severity_badge(analysis.get('severity', 'Unknown'))}", unsafe_allow_html=True)
        with col2:
            st.markdown(f"**Confidence:** {render_confidence_bar(analysis.get('confidence', 0))}", unsafe_allow_html=True)
        with col3:
            st.caption(f"Incident ID: `{incident_id}` | {datetime.utcnow().strftime('%H:%M:%S UTC')}")

        # Likely Root Cause (Hypothesis)
        st.markdown("""
        <div class="hypothesis-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong>🎯 Likely Root Cause (AI Hypothesis)</strong>
                <span class="hypothesis-badge">🤖 HYPOTHESIS</span>
            </div>
            <div>{}</div>
        </div>
        """.format(analysis.get('likely_root_cause', 'N/A')), unsafe_allow_html=True)

        # Explanation
        st.markdown("**📋 Explanation**")
        st.write(analysis.get('explanation', 'N/A'))

        # Recommended Actions
        st.markdown("**🛠️ Recommended Actions**")
        for i, action in enumerate(analysis.get('recommended_actions', []), 1):
            st.markdown(f"{i}. {action}")

        # Memory Influence
        if analysis.get('memory_influence'):
            st.markdown("""
            <div style="background-color: #f0fdfa; border: 1px solid #0d9488; border-radius: 6px; padding: 12px; margin: 12px 0;">
                <strong>🧠 Memory Influence:</strong><br>
                {}
            </div>
            """.format(analysis['memory_influence']), unsafe_allow_html=True)

        # Historical Matches
        historical_matches = analysis.get('historical_matches', [])
        if historical_matches:
            st.markdown("**📚 Retrieved Historical Matches**")
            st.caption("These are verified past incidents from team memory (teal = memory)")
            for match in historical_matches:
                render_historical_match(match)
        else:
            st.info("No relevant historical incidents found in team memory. This analysis is based on general patterns only.")

        # Caveats
        if analysis.get('caveats'):
            st.warning(f"⚠️ **Caveats:** {analysis['caveats']}")

        # Resolution Confirmation
        st.divider()
        st.subheader("✅ Confirm Resolution")
        st.markdown("After investigating, confirm the actual root cause and resolution to teach the system.")

        with st.form("resolution_form"):
            verified_root_cause = st.text_area(
                "Verified Root Cause *",
                placeholder="What was the actual root cause? (e.g., 'Connection leak in UserService.getUserProfile() - missing try-with-resources')",
                height=80
            )

            verified_resolution = st.text_area(
                "Verified Resolution *",
                placeholder="What steps fixed it? (e.g., 'Added try-with-resources to DB connections. Increased pool size. Deployed v2.3.1.')",
                height=100
            )

            notes = st.text_area(
                "Notes (optional)",
                placeholder="Additional context, links to PRs, monitoring dashboards, etc.",
                height=60
            )

            confirm_submitted = st.form_submit_button("💾 Save Verified Resolution", type="primary")

        if confirm_submitted:
            if not verified_root_cause or not verified_resolution:
                st.error("Please provide both verified root cause and resolution")
            else:
                with st.spinner("Saving to team memory..."):
                    result = api_client.confirm_resolution(
                        incident_id=incident_id,
                        verified_root_cause=verified_root_cause,
                        verified_resolution=verified_resolution,
                        notes=notes if notes else None
                    )

                if result.success:
                    st.success("✅ Verified resolution saved to team memory!")
                    st.balloons()
                    # Show confirmation
                    st.markdown("""
                    <div class="verified-box">
                        <strong>💾 Verified Learning Stored</strong><br>
                        <span class="verified-badge">✅ VERIFIED</span><br>
                        This resolution will help future incidents.
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(f"Failed to save: {result.error}")


# ============================================================================
# Page: Memory Explorer
# ============================================================================

elif page == "📚 Memory Explorer":
    st.header("Memory Explorer")
    st.markdown("Browse verified incident memories retained in team memory.")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh Memories"):
            st.rerun()

    with st.spinner("Loading memories..."):
        result = api_client.list_memories(limit=50)

    if result.success:
        memories = result.data.get("memories", [])
        total = result.data.get("total", 0)

        st.caption(f"Showing {len(memories)} of {total} memories")

        if memories:
            # Filter options
            services = sorted({m.get("service_name", "Unknown") for m in memories})
            selected_service = st.selectbox("Filter by Service", ["All", *services])

            filtered = memories if selected_service == "All" else [
                m for m in memories if m.get("service_name") == selected_service
            ]

            for memory in filtered:
                with st.expander(f"{memory.get('incident_id', 'Unknown')} — {memory.get('service_name', 'Unknown')}"):
                    st.markdown("""
                    <div class="verified-box">
                        <span class="verified-badge">✅ VERIFIED</span>
                    </div>
                    """, unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Symptom**")
                        st.write(memory.get("symptom", "N/A"))
                        st.markdown("**Verified Root Cause**")
                        st.write(memory.get("verified_root_cause", "N/A"))
                    with col2:
                        st.markdown("**Verified Resolution**")
                        st.write(memory.get("verified_resolution", "N/A"))
                        st.markdown("**Memory ID**")
                        st.code(memory.get("memory_id", "N/A"))
        else:
            st.info("No memories found. Seed the memory bank with `python scripts/seed_memory.py` or confirm resolutions from analyses.")
    else:
        st.error(f"Failed to load memories: {result.error}")


# ============================================================================
# Page: Insights
# ============================================================================

elif page == "📊 Insights":
    st.header("System Insights")
    st.markdown("Recurring patterns and themes derived from team memory reflection.")

    with st.spinner("Loading insights..."):
        result = api_client.get_insights()

    if result.success:
        insights = result.data.get("insights", [])

        if insights:
            for insight in insights:
                with st.expander(f"🔍 {insight.get('theme', 'Unknown Pattern')}"):
                    st.write(insight.get("description", "No description"))

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Related Incidents", insight.get("incident_count", 0))
                    with col2:
                        examples = insight.get("example_incidents", [])
                        if examples:
                            st.write("**Example Incidents:**")
                            for ex in examples:
                                st.code(ex)
        else:
            st.info("No insights available yet. Add more verified incidents to enable pattern detection.")
    else:
        st.error(f"Failed to load insights: {result.error}")


# ============================================================================
# Page: History
# ============================================================================

elif page == "📜 History":
    st.header("Analysis History")
    st.markdown("Previous incident analyses from this session.")

    if st.session_state.analysis_history:
        for i, analysis in enumerate(st.session_state.analysis_history):
            incident_id = analysis.get("incident_id", f"unknown-{i}")
            severity = analysis.get("severity", "Unknown")
            service = analysis.get("service_name", "Unknown")  # Not in response, would need to fetch
            cause = analysis.get("likely_root_cause", "N/A")[:80]

            with st.expander(f"{incident_id} — {render_severity_badge(severity)} — {cause}...", expanded=False):
                st.json(analysis)
    else:
        st.info("No analyses in this session yet. Submit an incident on the Analyze page.")


# ============================================================================
# Footer
# ============================================================================

st.divider()
st.caption("""
**RecallOps** — AI-assisted incident response with persistent memory.
Teal = Team Memory | Amber = AI Hypothesis | Violet = Human Verified
""")
