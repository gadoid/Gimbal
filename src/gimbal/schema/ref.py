from pydantic import BaseModel, Field, model_validator, ConfigDict

class RefBase(BaseModel) :
    ref : str


if __name__ == "__main__":
    # 测试 RefBase 实例化
    ref = RefBase(ref="test_ref")
    print(f"RefBase 测试: ref={ref.ref}")
