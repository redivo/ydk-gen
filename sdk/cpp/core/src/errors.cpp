/// YANG Development Kit
// Copyright 2016 Cisco Systems. All rights reserved
//
////////////////////////////////////////////////////////////////
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
//  Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//
//////////////////////////////////////////////////////////////////


#include "path/path_private.hpp"

/////////////////////////////////////////////////////////////////////////
/// YCPPError
/////////////////////////////////////////////////////////////////////////
ydk::YCPPError::YCPPError(const std::string& msg) : err_msg{msg}
{
	what();
}

const char* ydk::YCPPError::what() const noexcept
{
	return err_msg.c_str();
}

/////////////////////////////////////////////////////////////////////////
/// YCPPCoreError
/////////////////////////////////////////////////////////////////////////
ydk::path::YCPPCoreError::YCPPCoreError(const std::string& msg) : ydk::YCPPError{msg}
{

}

//////////////////////////////////////////////////////////////////////////
/// YCPPIllegalStateError
//////////////////////////////////////////////////////////////////////////
ydk::YCPPIllegalStateError::YCPPIllegalStateError(const std::string& msg) : ydk::YCPPError{msg}
{

}

//////////////////////////////////////////////////////////////////////////
/// YCPPInvalidArgumentError
//////////////////////////////////////////////////////////////////////////
ydk::YCPPInvalidArgumentError::YCPPInvalidArgumentError(const std::string& msg) : ydk::YCPPError{msg}
{

}

//////////////////////////////////////////////////////////////////////////
/// YCPPOperationNotSupportedError
//////////////////////////////////////////////////////////////////////////
ydk::YCPPOperationNotSupportedError::YCPPOperationNotSupportedError(const std::string& msg) : ydk::YCPPError{msg}
{

}

//////////////////////////////////////////////////////////////////////////
/// YCPPDataValidationError
//////////////////////////////////////////////////////////////////////////
ydk::path::YCPPDataValidationError::YCPPDataValidationError() : ydk::path::YCPPCoreError{"Data Validation Error"}
{

}

//////////////////////////////////////////////////////////////////////////
/// YCPPPathError
//////////////////////////////////////////////////////////////////////////
ydk::path::YCPPPathError::YCPPPathError(ydk::path::YCPPPathError::Error error_code) : ydk::path::YCPPCoreError{"Data Validation Error"}, err{error_code}
{

}



/////////////////////////////////////////////////////////////////////////
/// YCPPCodecError
/////////////////////////////////////////////////////////////////////////
ydk::path::YCPPCodecError::YCPPCodecError(YCPPCodecError::Error ec) : YCPPCoreError(ly_errmsg()), err{ec}
{

}


/////////////////////////////////////////////////////////////////////////
/// YCPPModelError
/////////////////////////////////////////////////////////////////////////
ydk::YCPPModelError::YCPPModelError(const std::string& msg) : ydk::YCPPError{msg}
{

}
