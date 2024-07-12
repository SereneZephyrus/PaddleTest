import os
os.environ['FLAGS_cinn_new_group_scheduler'] = '1'
os.environ['FLAGS_group_schedule_tiling_first'] = '1'
os.environ['FLAGS_enable_pir_api'] = '1'
os.environ['FLAGS_cinn_bucket_compile'] = '1'
import sys
import unittest
import numpy as np
from dataclasses import dataclass
import typing as t

@dataclass
class Stage:
    name: str
    env_vars: t.Dict[str, str]

cinn_stages = [
    Stage(
        name="dynamic_to_static",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=False,
            FLAGS_prim_enable_dynamic=False,
        ),
    ),
    Stage(
        name="prim",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
        ),
    ),
    Stage(
        name="infer_symbolic",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=False,
            FLAGS_check_infer_symbolic=True,
        ),
    ),
	Stage(
        name="frontend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=True,
        ), 
    ),
    Stage(
        name="backend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=False,
        ), 
    ),
]

def GetCinnStageByName(name):
    for stage in cinn_stages:
        if stage.name == name:
            return stage
    return None

def GetCurrentCinnStage():
    name = os.getenv('PADDLE_DEBUG_CINN_STAGE_NAME')
    if name is None:
        return None
    stage_names = [stage.name for stage in cinn_stages]
    assert name in stage_names, (
        f"PADDLE_DEBUG_CINN_STAGE_NAME should be in {stage_names}"
    )
    return GetCinnStageByName(name)

def GetPrevCinnStage(stage):
    for i in range(1, len(cinn_stages)):
        if stage is cinn_stages[i]:
            return cinn_stages[i - 1]
    return None

def IsCinnStageEnableDiff():
    value = os.getenv('PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF')
    enabled = value in {
        '1',
        'true',
        'True',
    }
    if enabled:
        assert GetCurrentCinnStage() is not None
    return enabled

def GetExitCodeAndStdErr(cmd, env):
    env = {
        k:v
        for k, v in env.items()
        if v is not None
    }
    import subprocess
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    return result.returncode, result.stderr

def GetStageExitCodeAndStdErr(stage):
    return GetExitCodeAndStdErr(
        [sys.executable, __file__],
        env=dict(
            PADDLE_DEBUG_CINN_STAGE_NAME=stage.name,
            PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF='0',
            PYTHONPATH=os.getenv('PYTHONPATH'),
            ATHENA_ENABLE_TRY_RUN="False",
        ),
    )

def AthenaTryRunEnabled():
    return os.getenv('ATHENA_ENABLE_TRY_RUN') not in {
        "0",
        "False",
        "false",
        "OFF"
    }

def GetNeedSkipAndSkipMessage():
    current_stage = GetCurrentCinnStage()
    assert current_stage is not None
    if not IsCinnStageEnableDiff():
        return False, ""
    last_stage = GetPrevCinnStage(current_stage)
    if last_stage is None:
        return False, ""
    exitcode, stderr = GetStageExitCodeAndStdErr(last_stage)
    if exitcode != 0:
        return True, f"last stage failed. stderr: {stderr}"
    return False, ""

def GetCurrentStageTryRunExitCodeAndStdErr():
    if not AthenaTryRunEnabled():
        return False, ""
    current_stage = GetCurrentCinnStage()
    assert current_stage is not None
    return GetStageExitCodeAndStdErr(current_stage)

def SetDefaultEnv(**env_var2value):
    for env_var, value in env_var2value.items():
        if os.getenv(env_var) is None:
            os.environ[env_var] = str(value)

SetDefaultEnv(
    PADDLE_DEBUG_CINN_STAGE_NAME="backend",
    PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF=False,
    PADDLE_DEBUG_ENABLE_CINN=True,
    FLAGS_enable_pir_api=True,
    FLAGS_prim_all=True,
    FLAGS_prim_enable_dynamic=True,
    FLAGS_use_cinn=False,
    FLAGS_check_infer_symbolic=False,
    FLAGS_enable_fusion_fallback=False,
)

need_skip, skip_message = GetNeedSkipAndSkipMessage()
try_run_exit_code, try_run_stderr = GetCurrentStageTryRunExitCodeAndStdErr()

import paddle

def SetEnvVar(env_var2value):
    for env_var, value in env_var2value.items():
        os.environ[env_var] = str(value)
    paddle.set_flags({
        env_var:value
        for env_var, value in env_var2value.items()
        if env_var.startswith('FLAGS_')
    })

if GetCurrentCinnStage() is not None:
    SetEnvVar(GetCurrentCinnStage().env_vars)

def NumOperationsInBlock(block_idx):
    return [18][block_idx] - 1 # number-of-ops-in-block

def GetPaddleDebugNumAllowedOps():
    try:
        return int(os.getenv('PADDLE_DEBUG_NUM_ALLOWED_OPS'))
    except:
        return None

paddle_debug_num_allowed_ops = GetPaddleDebugNumAllowedOps()


if type(paddle_debug_num_allowed_ops) is not int:
    def EarlyReturn(block_idx, op_idx):
        return False      
else:
    def EarlyReturn(block_idx, op_idx):
        return op_idx >= paddle_debug_num_allowed_ops

class BlockEntries:

    def builtin_module_0_0_0(self, parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_0, parameter_6, parameter_7, data_3, data_0, data_1, data_2):

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_0 = paddle._C_ops.conv2d(data_0, parameter_0, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        # pd_op.full_int_array: (4xi64) <- ()
        full_int_array_0 = [1, -1, 1, 1]

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_0, reshape_1 = paddle.reshape(parameter_1, full_int_array_0), None

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_0 = conv2d_0 + reshape_0

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_1 = paddle._C_ops.conv2d(data_1, parameter_2, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_2, reshape_3 = paddle.reshape(parameter_3, full_int_array_0), None

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_1 = conv2d_1 + reshape_2

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_2 = paddle._C_ops.conv2d(data_2, parameter_4, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_4, reshape_5 = paddle.reshape(parameter_5, full_int_array_0), None

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_2 = conv2d_2 + reshape_4

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_3 = paddle._C_ops.conv2d(data_3, parameter_6, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_6, reshape_7 = paddle.reshape(parameter_7, full_int_array_0), None

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_3 = conv2d_3 + reshape_6

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, -1x19x-1x-1xf32)
        add_4 = add_0 + add_1

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, -1x19x-1x-1xf32)
        add_5 = add_4 + add_2

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, -1x19x-1x-1xf32)
        add_6 = add_5 + add_3

        # pd_op.full: (1xf32) <- ()
        full_0 = paddle._C_ops.full([1], 0.25, paddle.float32, paddle.core.CPUPlace())

        # pd_op.scale: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1xf32)
        scale_0 = paddle._C_ops.scale(add_6, full_0, 0, True)
        return conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5, full_0, scale_0



def GetEnvVarEnableJit():
    enable_jit = os.getenv('PADDLE_DEBUG_ENABLE_JIT')
    return enable_jit not in {
        "0",
        "False",
        "false",
        "OFF",
    }

def GetEnvVarEnableCinn():
    enable_cinn = os.getenv('PADDLE_DEBUG_ENABLE_CINN')
    return enable_cinn not in {
        "0",
        "False",
        "false",
        "OFF",
    }


def GetTolerance(dtype):
    if dtype == np.float16:
        return GetFloat16Tolerance()
    if dtype == np.float32:
        return GetFloat32Tolerance()
    return 1e-6

def GetFloat16Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT16_TOL'))
    except:
        return 1e-3

def GetFloat32Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT32_TOL'))
    except:
        return 1e-6

def IsInteger(dtype):
    return np.dtype(dtype).char in np.typecodes['AllInteger']


class CinnTestBase:
    def setUp(self):
        paddle.seed(2024)
        self.prepare_data()

    def _test_entry(self):
        dy_outs = self.entry(use_cinn=False)
        cinn_outs = self.entry(use_cinn=GetEnvVarEnableCinn())

        for cinn_out, dy_out in zip(cinn_outs, dy_outs):
          if type(cinn_out) is list and type(dy_out) is list:
            for x, y in zip(cinn_out, dy_out):
              self.assert_all_close(x, y)
          else:
            self.assert_all_close(cinn_out, dy_out)

    def assert_all_close(self, x, y):
        if (hasattr(x, "numpy") and hasattr(y, "numpy")):
            x_numpy = x.numpy()
            y_numpy = y.numpy()
            assert x_numpy.dtype == y_numpy.dtype
            if IsInteger(x_numpy.dtype):
                np.testing.assert_equal(x_numpy, y_numpy)
            else:
                tol = GetTolerance(x_numpy.dtype)
                np.testing.assert_allclose(x_numpy, y_numpy, atol=tol, rtol=tol)
        else:
            assert x == y

class Block_builtin_module_0_0_0(paddle.nn.Layer, BlockEntries):
    def __init__(self):
        super().__init__()

    def forward(self, parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_0, parameter_6, parameter_7, data_3, data_0, data_1, data_2):
        args = [parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_0, parameter_6, parameter_7, data_3, data_0, data_1, data_2]
        for op_idx, op_func in enumerate(self.get_op_funcs()):
            if EarlyReturn(0, op_idx):
                return args
            args = op_func(*args)
        return args

    def get_op_funcs(self):
        return [
            self.op_conv2d_0,
            self.op_full_int_array_0,
            self.op_reshape_0,
            self.op_add_0,
            self.op_conv2d_1,
            self.op_reshape_1,
            self.op_add_1,
            self.op_conv2d_2,
            self.op_reshape_2,
            self.op_add_2,
            self.op_conv2d_3,
            self.op_reshape_3,
            self.op_add_3,
            self.op_add_4,
            self.op_add_5,
            self.op_add_6,
            self.op_full_0,
            self.op_scale_0,
        ]

    def op_conv2d_0(self, parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_0, parameter_6, parameter_7, data_3, data_0, data_1, data_2):
    
        # EarlyReturn(0, 0)

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_0 = paddle._C_ops.conv2d(data_0, parameter_0, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        return [parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0]

    def op_full_int_array_0(self, parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0):
    
        # EarlyReturn(0, 1)

        # pd_op.full_int_array: (4xi64) <- ()
        full_int_array_0 = [1, -1, 1, 1]

        return [parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0, full_int_array_0]

    def op_reshape_0(self, parameter_5, parameter_2, parameter_3, parameter_4, parameter_1, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0, full_int_array_0):
    
        # EarlyReturn(0, 2)

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_0, reshape_1 = paddle.reshape(parameter_1, full_int_array_0), None

        return [parameter_5, parameter_2, parameter_3, parameter_4, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1]

    def op_add_0(self, parameter_5, parameter_2, parameter_3, parameter_4, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1):
    
        # EarlyReturn(0, 3)

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_0 = conv2d_0 + reshape_0

        return [parameter_5, parameter_2, parameter_3, parameter_4, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0]

    def op_conv2d_1(self, parameter_5, parameter_2, parameter_3, parameter_4, parameter_6, parameter_7, data_3, data_1, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0):
    
        # EarlyReturn(0, 4)

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_1 = paddle._C_ops.conv2d(data_1, parameter_2, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        return [parameter_5, parameter_3, parameter_4, parameter_6, parameter_7, data_3, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1]

    def op_reshape_1(self, parameter_5, parameter_3, parameter_4, parameter_6, parameter_7, data_3, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1):
    
        # EarlyReturn(0, 5)

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_2, reshape_3 = paddle.reshape(parameter_3, full_int_array_0), None

        return [parameter_5, parameter_4, parameter_6, parameter_7, data_3, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3]

    def op_add_1(self, parameter_5, parameter_4, parameter_6, parameter_7, data_3, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3):
    
        # EarlyReturn(0, 6)

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_1 = conv2d_1 + reshape_2

        return [parameter_5, parameter_4, parameter_6, parameter_7, data_3, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1]

    def op_conv2d_2(self, parameter_5, parameter_4, parameter_6, parameter_7, data_3, data_2, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1):
    
        # EarlyReturn(0, 7)

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_2 = paddle._C_ops.conv2d(data_2, parameter_4, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        return [parameter_5, parameter_6, parameter_7, data_3, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2]

    def op_reshape_2(self, parameter_5, parameter_6, parameter_7, data_3, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2):
    
        # EarlyReturn(0, 8)

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_4, reshape_5 = paddle.reshape(parameter_5, full_int_array_0), None

        return [parameter_6, parameter_7, data_3, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5]

    def op_add_2(self, parameter_6, parameter_7, data_3, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5):
    
        # EarlyReturn(0, 9)

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_2 = conv2d_2 + reshape_4

        return [parameter_6, parameter_7, data_3, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2]

    def op_conv2d_3(self, parameter_6, parameter_7, data_3, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2):
    
        # EarlyReturn(0, 10)

        # pd_op.conv2d: (-1x19x-1x-1xf32) <- (-1x32x-1x-1xf32, 19x32x1x1xf32)
        conv2d_3 = paddle._C_ops.conv2d(data_3, parameter_6, [1, 1], [0, 0], 'EXPLICIT', [1, 1], 1, 'NCHW')

        return [parameter_7, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3]

    def op_reshape_3(self, parameter_7, conv2d_0, full_int_array_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3):
    
        # EarlyReturn(0, 11)

        # pd_op.reshape: (1x19x1x1xf32, 0x19xi64) <- (19xf32, 4xi64)
        reshape_6, reshape_7 = paddle.reshape(parameter_7, full_int_array_0), None

        return [conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7]

    def op_add_3(self, conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7):
    
        # EarlyReturn(0, 12)

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1x19x1x1xf32)
        add_3 = conv2d_3 + reshape_6

        return [conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3]

    def op_add_4(self, conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3):
    
        # EarlyReturn(0, 13)

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, -1x19x-1x-1xf32)
        add_4 = add_0 + add_1

        return [conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4]

    def op_add_5(self, conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4):
    
        # EarlyReturn(0, 14)

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, -1x19x-1x-1xf32)
        add_5 = add_4 + add_2

        return [conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5]

    def op_add_6(self, conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5):
    
        # EarlyReturn(0, 15)

        # pd_op.add: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, -1x19x-1x-1xf32)
        add_6 = add_5 + add_3

        return [conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5, add_6]

    def op_full_0(self, conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5, add_6):
    
        # EarlyReturn(0, 16)

        # pd_op.full: (1xf32) <- ()
        full_0 = paddle._C_ops.full([1], 0.25, paddle.float32, paddle.core.CPUPlace())

        return [conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5, add_6, full_0]

    def op_scale_0(self, conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5, add_6, full_0):
    
        # EarlyReturn(0, 17)

        # pd_op.scale: (-1x19x-1x-1xf32) <- (-1x19x-1x-1xf32, 1xf32)
        scale_0 = paddle._C_ops.scale(add_6, full_0, 0, True)

        return [conv2d_0, reshape_0, reshape_1, add_0, conv2d_1, reshape_2, reshape_3, add_1, conv2d_2, reshape_4, reshape_5, add_2, conv2d_3, reshape_6, reshape_7, add_3, add_4, add_5, full_0, scale_0]

@unittest.skipIf(need_skip, skip_message)
class Test_builtin_module_0_0_0(CinnTestBase, unittest.TestCase):
    def prepare_data(self):
        self.inputs = [
            # parameter_5
            paddle.uniform([19], dtype='float32', min=0, max=0.5),
            # parameter_2
            paddle.uniform([19, 32, 1, 1], dtype='float32', min=0, max=0.5),
            # parameter_3
            paddle.uniform([19], dtype='float32', min=0, max=0.5),
            # parameter_4
            paddle.uniform([19, 32, 1, 1], dtype='float32', min=0, max=0.5),
            # parameter_1
            paddle.uniform([19], dtype='float32', min=0, max=0.5),
            # parameter_0
            paddle.uniform([19, 32, 1, 1], dtype='float32', min=0, max=0.5),
            # parameter_6
            paddle.uniform([19, 32, 1, 1], dtype='float32', min=0, max=0.5),
            # parameter_7
            paddle.uniform([19], dtype='float32', min=0, max=0.5),
            # data_3
            paddle.uniform([1, 32, 512, 1024], dtype='float32', min=0, max=0.5),
            # data_0
            paddle.uniform([1, 32, 512, 1024], dtype='float32', min=0, max=0.5),
            # data_1
            paddle.uniform([1, 32, 512, 1024], dtype='float32', min=0, max=0.5),
            # data_2
            paddle.uniform([1, 32, 512, 1024], dtype='float32', min=0, max=0.5),
        ]
        for input in self.inputs:
            input.stop_gradient = True

    def apply_to_static(self, net, use_cinn):
        build_strategy = paddle.static.BuildStrategy()
        input_spec = [
            # parameter_5
            paddle.static.InputSpec(shape=[19], dtype='float32'),
            # parameter_2
            paddle.static.InputSpec(shape=[19, 32, 1, 1], dtype='float32'),
            # parameter_3
            paddle.static.InputSpec(shape=[19], dtype='float32'),
            # parameter_4
            paddle.static.InputSpec(shape=[19, 32, 1, 1], dtype='float32'),
            # parameter_1
            paddle.static.InputSpec(shape=[19], dtype='float32'),
            # parameter_0
            paddle.static.InputSpec(shape=[19, 32, 1, 1], dtype='float32'),
            # parameter_6
            paddle.static.InputSpec(shape=[19, 32, 1, 1], dtype='float32'),
            # parameter_7
            paddle.static.InputSpec(shape=[19], dtype='float32'),
            # data_3
            paddle.static.InputSpec(shape=[None, 32, None, None], dtype='float32'),
            # data_0
            paddle.static.InputSpec(shape=[None, 32, None, None], dtype='float32'),
            # data_1
            paddle.static.InputSpec(shape=[None, 32, None, None], dtype='float32'),
            # data_2
            paddle.static.InputSpec(shape=[None, 32, None, None], dtype='float32'),
        ]
        build_strategy.build_cinn_pass = use_cinn
        return paddle.jit.to_static(
            net,
            input_spec=input_spec,
            build_strategy=build_strategy,
            full_graph=True,
        )

    def entry(self, use_cinn):
        net = Block_builtin_module_0_0_0()
        if GetEnvVarEnableJit():
            net = self.apply_to_static(net, use_cinn)
        paddle.seed(2024)
        out = net(*self.inputs)
        return out

    def test_entry(self):
        if AthenaTryRunEnabled():
            if try_run_exit_code == 0:
                # All unittest cases passed.
                return
            if try_run_exit_code < 0:
                # program paniced.
                raise RuntimeError(f"panicked. stderr: \n{try_run_stderr}")
        self._test_entry()

if __name__ == '__main__':
    unittest.main()