import sys
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from maa.tasker import Tasker


@AgentServer.custom_action("UpdateStageByOcr")
class UpdateStageByOcr(CustomAction):

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 1. 取本节点(getVitality)的 OCR 结果，格式如 "60/60"
        reco_detail = argv.reco_detail
        if not reco_detail or not reco_detail.hit or not reco_detail.best_result:
            print("UpdateStageByOcr: OCR did not hit, skip override")
            return False

        ocr_text = reco_detail.best_result.text  # e.g. "60/60"
        print(f"UpdateStageByOcr: OCR raw text = {ocr_text!r}")

        # 2. 解析出斜杠前的当前体力值 remain_vitality
        try:
            remain_vitality_str = ocr_text.split("/")[0].strip()
            remain_vitality = int(remain_vitality_str)
        except (ValueError, IndexError):
            print(
                f"UpdateStageByOcr: failed to parse remain_vitality from {ocr_text!r}"
            )
            return False

        print(f"UpdateStageByOcr: remain_vitality = {remain_vitality}")

        # 3. 读取“极品特招”选项对应的标记节点状态
        flag_node = context.get_node_object("specialTravel")
        perfect_recruit_enabled = bool(flag_node.enabled) if flag_node else False
        print(f"UpdateStageByOcr: perfect_recruit_enabled = {perfect_recruit_enabled}")

        # 4. 按规则计算 max_hit
        divisor = 20 if perfect_recruit_enabled else 5
        max_hit = remain_vitality // divisor
        print(f"UpdateStageByOcr: divisor={divisor}, computed max_hit={max_hit}")

        # 5. 写回 checkTravelStatus 的 max_hit 字段
        context.override_pipeline({"checkTravelStatus": {"max_hit": max_hit}})

        return True


def main():
    Tasker.set_log_dir("./debug")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        exit(1)

    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
