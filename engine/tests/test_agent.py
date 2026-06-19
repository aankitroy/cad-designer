from app.agent import run_agent


class FakeBlock:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)

    def create(self, **kwargs):
        return self._scripted.pop(0)


class FakeClient:
    def __init__(self, scripted):
        self.messages = FakeMessages(scripted)


def test_agent_executes_tool_then_finishes(sample_doc):
    h = sample_doc["line_handle"]
    scripted = [
        FakeResponse(
            "tool_use",
            [
                FakeBlock(type="text", text="Moving it."),
                FakeBlock(
                    type="tool_use",
                    id="t1",
                    name="move_entity",
                    input={"handle": h, "dx_m": -2.0, "dy_m": 0.0},
                ),
            ],
        ),
        FakeResponse("end_turn", [FakeBlock(type="text", text="Done — moved 2m left.")]),
    ]
    out = run_agent(
        client=FakeClient(scripted),
        doc=sample_doc["doc"],
        user_message="move the fixture 2m left",
        model="claude-sonnet-4-6",
    )
    assert out["reply"] == "Done — moved 2m left."
    assert len(out["changes"]) == 1
    assert out["changes"][0]["op"] == "move_entity"
    line = sample_doc["doc"].entitydb[h]
    assert abs(line.dxf.start.x - 0.0) < 1e-6  # was 2.0, moved -2


def test_agent_includes_component_context(sample_doc):
    captured = {}

    class CapturingMessages:
        def create(self, **kwargs):
            captured["messages"] = kwargs["messages"]
            return FakeResponse("end_turn", [FakeBlock(type="text", text="ok")])

    class CapturingClient:
        messages = CapturingMessages()

    run_agent(
        client=CapturingClient(),
        doc=sample_doc["doc"],
        user_message="place it by the door",
        components=["chair"],
    )
    first = captured["messages"][0]["content"]
    assert "chair" in first
